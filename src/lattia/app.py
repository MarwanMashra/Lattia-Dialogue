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
from .core import generate_opening_question, generate_reply
from .db import Base, engine, get_db
from .warmup import run_warmups


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
    p = models.Profile(name=payload.name, health_data={})
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
        profile_dict = {
            "id": p.id,
            "name": p.name,
            "is_done": p.is_done,
            "health_data": p.health_data,
        }
        opening = generate_opening_question(profile_dict)
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
        profile_dict = {
            "id": p.id,
            "name": p.name,
            "is_done": p.is_done,
            "health_data": p.health_data,
        }
        opening = generate_opening_question(profile_dict)
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
    # Rate limit per profile
    bucket = get_bucket(profile_id)
    if not bucket.allow():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this profile. Try again shortly.",
        )

    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Save user message
    user_msg = models.Message(profile_id=p.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()

    # Fetch history in plain dicts for your logic
    msgs = (
        db.execute(
            select(models.Message)
            .where(models.Message.profile_id == profile_id)
            .order_by(models.Message.created_at.asc())
        )
        .scalars()
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in msgs]

    # Run your logic
    profile_dict = {
        "id": p.id,
        "name": p.name,
        "is_done": p.is_done,
        "health_data": p.health_data,
    }
    llm_output = generate_reply(profile_dict, history, payload.content, p.is_done)

    if llm_output.is_done:
        p.is_done = True
        db.add(p)
        db.commit()

    # Optional health_data deep merge
    if llm_output.health_update:
        import copy

        new_hd = copy.deepcopy(p.health_data) if p.health_data else {}

        def deep_merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    deep_merge(a[k], v)
                else:
                    a[k] = v

        deep_merge(new_hd, llm_output.health_update)
        p.health_data = new_hd

    db.add(p)
    bot_msg = models.Message(
        profile_id=p.id, role="assistant", content=llm_output.reply
    )
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)

    return bot_msg


@app.get("/api/profiles/{profile_id}/health", response_model=schemas.HealthData)
def get_health(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"health_data": p.health_data or {}}


@app.put("/api/profiles/{profile_id}/health", response_model=schemas.HealthData)
def put_health(
    profile_id: int, payload: schemas.HealthData, db: Session = Depends(get_db)
):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    p.health_data = payload.health_data or {}
    db.add(p)
    db.commit()
    return {"health_data": p.health_data or {}}


@app.patch("/api/profiles/{profile_id}/status", response_model=schemas.ProfileOut)
def update_status(
    profile_id: int, payload: schemas.StatusUpdate, db: Session = Depends(get_db)
):
    p = db.get(models.Profile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    p.is_done = bool(payload.is_done)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p
