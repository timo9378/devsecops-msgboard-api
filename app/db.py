"""asyncpg connection pool. Pool 在 app 啟動時建立，shutdown 時關閉。"""

import asyncpg
import logging
from contextlib import asynccontextmanager
from app.config import settings

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    log.info(
        "connecting to postgres at %s:%s/%s as %s",
        settings.database_host,
        settings.database_port,
        settings.database_name,
        settings.database_user,
    )
    _pool = await asyncpg.create_pool(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.database_user,
        password=settings.database_password,
        database=settings.database_name,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id SERIAL PRIMARY KEY,
              username VARCHAR(50) UNIQUE NOT NULL,
              password_hash VARCHAR(255) NOT NULL,
              created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS messages (
              id SERIAL PRIMARY KEY,
              user_id INT REFERENCES users(id) ON DELETE CASCADE,
              content TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_messages_created
              ON messages(created_at DESC);
            """
        )
    log.info("postgres pool ready, schema verified")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("db pool not initialized")
    return _pool


@asynccontextmanager
async def conn():
    """Convenience: `async with conn() as c: await c.fetch(...)`"""
    async with pool().acquire() as c:
        yield c
