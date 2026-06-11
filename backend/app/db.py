"""Pool de conexões Postgres (psycopg3) + helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

# search_path garante que todas as queries usem o schema radar por padrão
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=8,
            kwargs={"options": f"-c search_path={settings.db_schema},public"},
            open=True,
        )
    return _pool


@contextmanager
def cursor() -> Iterator[Any]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            yield cur


def query_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


def ping() -> bool:
    try:
        with cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
        return True
    except Exception:
        return False
