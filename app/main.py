"""FastAPI app entry — message board API.

Endpoints:
  POST /api/auth/register   -> create user
  POST /api/auth/login      -> issue JWT
  GET  /api/messages        -> list all (public)
  POST /api/messages        -> post a message (auth)
  GET  /api/health          -> liveness probe
  GET  /api/health/ready    -> readiness probe (200 only if DB reachable)
"""

import logging
import os
import socket
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app import db, auth

logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger(__name__)

POD_NAME = os.environ.get("POD_NAME") or socket.gethostname()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    yield
    await db.close_pool()


app = FastAPI(
    title="Message Board API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_pod_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["x-pod-name"] = POD_NAME
    return response


# ── Pydantic models ──────────────────────────────
class AuthIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class MessageOut(BaseModel):
    id: int
    username: str
    content: str
    created_at: str


# ── Auth routes ──────────────────────────────────
@app.post("/api/auth/register", response_model=TokenOut, status_code=201)
async def register(body: AuthIn):
    async with db.conn() as c:
        existing = await c.fetchval(
            "SELECT id FROM users WHERE username = $1", body.username
        )
        if existing:
            raise HTTPException(status_code=409, detail="username taken")
        user_id = await c.fetchval(
            "INSERT INTO users(username, password_hash) VALUES($1, $2) RETURNING id",
            body.username,
            auth.hash_password(body.password),
        )
    token = auth.issue_token(user_id, body.username)
    return TokenOut(access_token=token, username=body.username)


@app.post("/api/auth/login", response_model=TokenOut)
async def login(body: AuthIn):
    async with db.conn() as c:
        row = await c.fetchrow(
            "SELECT id, password_hash FROM users WHERE username = $1", body.username
        )
    if row is None or not auth.verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = auth.issue_token(row["id"], body.username)
    return TokenOut(access_token=token, username=body.username)


# ── Message routes ───────────────────────────────
@app.get("/api/messages", response_model=list[MessageOut])
async def list_messages(limit: int = 50):
    """公開列表，不需登入。"""
    limit = min(max(limit, 1), 200)
    async with db.conn() as c:
        rows = await c.fetch(
            """
            SELECT m.id, u.username, m.content, m.created_at
            FROM messages m JOIN users u ON u.id = m.user_id
            ORDER BY m.created_at DESC LIMIT $1
            """,
            limit,
        )
    return [
        MessageOut(
            id=r["id"],
            username=r["username"],
            content=r["content"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


@app.post("/api/messages", response_model=MessageOut, status_code=201)
async def post_message(body: MessageIn, user: dict = Depends(auth.current_user)):
    async with db.conn() as c:
        row = await c.fetchrow(
            """
            INSERT INTO messages(user_id, content) VALUES($1, $2)
            RETURNING id, content, created_at
            """,
            user["id"],
            body.content,
        )
    return MessageOut(
        id=row["id"],
        username=user["username"],
        content=row["content"],
        created_at=row["created_at"].isoformat(),
    )


# ── Health probes ────────────────────────────────
@app.get("/api/health")
async def liveness():
    return {"status": "alive", "env": settings.app_env}


@app.get("/api/health/ready")
async def readiness():
    try:
        async with db.conn() as c:
            await c.fetchval("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db unreachable: {e}")
