# L'Attia Dialogue

Single `docker compose up` gives you:
- FastAPI backend on http://localhost:8000
- Landing page + Chat UI + Dashboard overlay at http://localhost:8000

## Quick start

```bash
docker compose up --build
# open http://localhost:8000
```

Data persists in a Postgres volume named `pgdata`.

## Project layout

```
.
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── src/
│   └── lattia/
│       ├── __init__.py
│       ├── main.py          # FastAPI app, routes, static
│       ├── db.py            # SQLAlchemy engine and session
│       ├── models.py        # SQLAlchemy ORM models
│       ├── schemas.py       # Pydantic models
│       ├── logic.py         # TODO spots for your chat logic
│       └── static/
│           ├── index.html   # Home: profile list, create, delete
│           ├── chat.html    # Chat UI + Dashboard overlay
│           ├── style.css    # Modern, clean styling
│           └── app.js       # Vanilla JS for UI interactions
└── README.md
```

## Notes

- No npm needed. Pure HTML/CSS/JS served by FastAPI.
- Replace the TODO sections in `logic.py` with your real logic.
- API docs at http://localhost:8000/docs

## Default API contract

- `GET /api/profiles` → list profiles
- `POST /api/profiles` body `{ "name": "Pablo" }` → create
- `DELETE /api/profiles/{profile_id}` → delete
- `GET /api/profiles/{profile_id}` → profile details
- `GET /api/profiles/{profile_id}/history` → chat history
- `POST /api/profiles/{profile_id}/start` → ensure first bot message exists, return it
- `POST /api/profiles/{profile_id}/messages` body `{ "content": "hi" }` → append user msg, call your logic, return assistant msg
- `GET /api/profiles/{profile_id}/health` → health JSON
- `PUT /api/profiles/{profile_id}/health` → replace health JSON
- `PATCH /api/profiles/{profile_id}/status` body `{ "is_done": true }` → mark interview done or not
