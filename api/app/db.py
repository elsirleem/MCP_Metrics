"""Database utilities for asyncpg connection pooling."""

import os
from typing import AsyncGenerator

import asyncpg


DATABASE_URL = os.getenv("DATABASE_URL", "postgres://mcp:mcp_password@localhost:5432/mcp_metrics")


async def init_pool() -> asyncpg.pool.Pool:
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


async def get_pool() -> AsyncGenerator[asyncpg.pool.Pool, None]:
    pool = await init_pool()
    try:
        yield pool
    finally:
        await pool.close()
