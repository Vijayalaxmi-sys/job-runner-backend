"""Connection pool helper. Adapt freely — this one is a starting point, not a rule."""

from __future__ import annotations

import os

from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]

_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)
    return _pool
