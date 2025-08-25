import time
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .core.agent import IntakeInterviewState, InterviewPayload, LattiaAgent
from .db import Base, engine, get_db
from .warmup import run_warmups

agent = LattiaAgent()


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity  # max tokens
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.timestamp = time.monotonic()
        self.lock = Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            # refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


_BUCKETS = {}
_BUCKETS_LOCK = Lock()
_BUCKET_CAPACITY = 30  # burst up to 10
_BUCKET_REFILL_RATE = _BUCKET_CAPACITY / 60  # ~10 messages per minute


def get_bucket(profile_id: int) -> TokenBucket:
    with _BUCKETS_LOCK:
        b = _BUCKETS.get(profile_id)
        if b is None:
            b = TokenBucket(_BUCKET_CAPACITY, _BUCKET_REFILL_RATE)
            _BUCKETS[profile_id] = b
        return b


# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # warmups
    run_warmups()

    yield
    # Shutdown
    engine.dispose()


app = FastAPI(title="L'Attia Dialogue", lifespan=lifespan)
# Static
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(static_dir / "index.html")


@app.get("/chat", include_in_schema=False)
def serve_chat():
    return FileResponse(static_dir / "chat.html")


# ---------------- API ----------------


@app.get("/api/profiles", response_model=list[schemas.ProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    profiles = (
        db.execute(select(models.Profile).order_by(models.Profile.created_at.desc()))
        .scalars()
        .all()
    )
    return profiles


@app.post("/api/profiles", response_model=schemas.ProfileOut)
def create_profile(payload: schemas.ProfileCreate, db: Session = Depends(get_db)):
    exists = db.execute(
        select(models.Profile).where(models.Profile.name == payload.name)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Profile name already exists")
    p = models.Profile(name=payload.name, interview_state={})
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@app.get("/api/profiles/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


@app.get("/api/profiles/{profile_id}/history", response_model=schemas.HistoryOut)
def get_history(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    msgs = (
        db.execute(
            select(models.Message)
            .where(models.Message.profile_id == profile_id)
            .order_by(models.Message.created_at.asc())
        )
        .scalars()
        .all()
    )
    return {"profile": p, "messages": msgs}


@app.post("/api/profiles/{profile_id}/start", response_model=schemas.MessageOut)
def ensure_opening_message(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    has_any = (
        db.execute(
            select(models.Message).where(models.Message.profile_id == profile_id)
        )
        .scalars()
        .first()
    )
    if not has_any:
        opening = agent.generate_opening_question(p.name)
        m = models.Message(profile_id=p.id, role="assistant", content=opening)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m
    last_assistant = (
        db.execute(
            select(models.Message)
            .where(
                models.Message.profile_id == profile_id,
                models.Message.role == "assistant",
            )
            .order_by(models.Message.created_at.desc())
        )
        .scalars()
        .first()
    )
    if not last_assistant:
        opening = agent.generate_opening_question(user_name=p.name)
        m = models.Message(profile_id=p.id, role="assistant", content=opening)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m
    return last_assistant


@app.post("/api/profiles/{profile_id}/messages", response_model=schemas.MessageOut)
def send_message(
    profile_id: int, payload: schemas.MessageCreate, db: Session = Depends(get_db)
):
    # rate limit
    bucket = get_bucket(profile_id)
    if not bucket.allow():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this profile. Try again shortly.",
        )

    # one transaction for everything
    try:
        with db.begin():  # ensures single commit or rollback
            # lock the profile row to prevent concurrent writes to interview_state
            p = (
                db.execute(
                    select(models.Profile)
                    .where(models.Profile.id == profile_id)
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not p:
                raise HTTPException(status_code=404, detail="Profile not found")

            # save user message
            user_msg = models.Message(
                profile_id=p.id, role="user", content=payload.content
            )
            db.add(user_msg)

            # fetch full history
            msgs = (
                db.execute(
                    select(models.Message)
                    .where(models.Message.profile_id == profile_id)
                    .order_by(models.Message.created_at.asc())
                )
                .scalars()
                .all()
            )
            history = [{"role": str(m.role), "content": str(m.content)} for m in msgs]

            # hydrate state, run agent
            interview_state = IntakeInterviewState.model_validate(p.interview_state)
            reply, interview_state = agent.generate_reply(
                user_query=payload.content,
                history=history,
                state=interview_state,
            )

            # persist updated state
            p.interview_state = interview_state.model_dump(exclude_none=True)

            # persist assistant message
            bot_msg = models.Message(profile_id=p.id, role="assistant", content=reply)
            db.add(bot_msg)

            # flush so bot_msg gets its id and timestamps before we return
            db.flush()
            db.refresh(bot_msg)

        # outside the 'with', transaction has been committed
        return bot_msg

    except HTTPException:
        # let FastAPI handle these
        raise
    except Exception as e:
        # safety net
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/api/profiles/{profile_id}/health", response_model=InterviewPayload)
def get_health(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    return IntakeInterviewState.model_validate(p.interview_state).payload
