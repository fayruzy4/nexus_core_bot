from __future__ import annotations

import asyncio
import os
import re
import ssl
import threading
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import asyncpg
except Exception as exc:  # pragma: no cover - import-time guard
    asyncpg = None  # type: ignore[assignment]
    _ASYNC_PG_IMPORT_ERROR = exc
else:
    _ASYNC_PG_IMPORT_ERROR = None


_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOOP_LOCK = threading.Lock()
_LOOP_THREAD: threading.Thread | None = None
_LOOP: asyncio.AbstractEventLoop | None = None
_POOL: "asyncpg.Pool | None" = None


class PostgresError(RuntimeError):
    pass


@dataclass(slots=True)
class PgConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl: str | bool | None = None
    min_size: int = 5
    max_size: int = 20
    statement_cache_size: int = 0

    @classmethod
    def from_env(cls) -> "PgConfig":
        url = (os.getenv("DATABASE_URL") or "").strip()
        if url:
            m = re.match(
                r"^postgres(?:ql)?://(?P<user>[^:]+):(?P<pw>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>[^?]+)",
                url,
            )
            if not m:
                raise PostgresError("DATABASE_URL tidak valid. Gunakan postgresql://user:pass@host:port/db")
            return cls(
                host=m.group("host"),
                port=int(m.group("port")),
                database=m.group("db"),
                user=m.group("user"),
                password=m.group("pw"),
            )

        host = os.getenv("PG_HOST", "").strip()
        port = int(os.getenv("PG_PORT", "6543"))
        database = os.getenv("PG_DATABASE", "postgres").strip()
        user = os.getenv("PG_USER", "").strip()
        password = os.getenv("PG_PASSWORD", "").strip()

        ssl_raw = os.getenv("PG_SSLMODE", "require").strip().lower()

        if ssl_raw in {"", "disable", "false", "0", "no"}:
            ssl_mode = None
        else:
            ssl_mode = ssl.create_default_context()
            ssl_mode.check_hostname = False
            ssl_mode.verify_mode = ssl.CERT_NONE

        return cls(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl=ssl_mode,
        )
        


class QueryResponse:
    __slots__ = ("data",)

    def __init__(self, data: Any = None) -> None:
        self.data = data


@dataclass(slots=True)
class _Condition:
    op: str
    column: str
    value: Any


@dataclass(slots=True)
class _Order:
    column: str
    desc: bool = False


def _quote_ident(name: str) -> str:
    if not _VALID_IDENT.match(name):
        raise PostgresError(f"Identifier tidak valid: {name!r}")
    return f'"{name}"'


def _ensure_asyncpg() -> None:
    if asyncpg is None:  # pragma: no cover - import-time guard
        raise RuntimeError(
            "asyncpg belum terpasang. Tambahkan asyncpg==0.30.0 ke requirements.txt",
        ) from _ASYNC_PG_IMPORT_ERROR


def _ensure_loop_thread() -> asyncio.AbstractEventLoop:
    global _LOOP_THREAD, _LOOP
    with _LOOP_LOCK:
        if _LOOP and _LOOP_THREAD and _LOOP_THREAD.is_alive():
            return _LOOP

        ready = threading.Event()

        def _runner() -> None:
            global _LOOP
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _LOOP = loop
            ready.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                loop.close()

        _LOOP_THREAD = threading.Thread(target=_runner, name="postgres-asyncpg-loop", daemon=True)
        _LOOP_THREAD.start()
        ready.wait()
        if _LOOP is None:
            raise PostgresError("Gagal membuat event loop PostgreSQL")
        return _LOOP


def _submit(coro: Any) -> Any:
    loop = _ensure_loop_thread()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


async def _ainit_pool() -> None:
    global _POOL
    _ensure_asyncpg()
    if _POOL is not None:
        return

    cfg = PgConfig.from_env()
    if not cfg.host or not cfg.user or not cfg.password:
        raise PostgresError("PG_HOST/PG_USER/PG_PASSWORD belum diisi. Atau set DATABASE_URL.")

    _POOL = await asyncpg.create_pool(
    host=cfg.host,
    port=cfg.port,
    database=cfg.database,
    user=cfg.user,
    password=cfg.password,
    ssl=cfg.ssl,
    min_size=1,
    max_size=1,
    statement_cache_size=0,
    )
async def _aclose_pool() -> None:
    global _POOL
    if _POOL is None:
        return
    await _POOL.close()
    _POOL = None


def init_pool() -> None:
    """Create the asyncpg pool on a background event loop."""
    _submit(_ainit_pool())


def close_pool() -> None:
    """Close the asyncpg pool and stop the background event loop."""
    global _LOOP, _LOOP_THREAD
    try:
        if _LOOP is not None and _LOOP.is_running():
            _submit(_aclose_pool())
    finally:
        if _LOOP is not None and _LOOP.is_running():
            _LOOP.call_soon_threadsafe(_LOOP.stop)
        if _LOOP_THREAD and _LOOP_THREAD.is_alive():
            _LOOP_THREAD.join(timeout=2.0)
        _LOOP = None
        _LOOP_THREAD = None


def _pool() -> "asyncpg.Pool":
    if _POOL is None:
        init_pool()
    if _POOL is None:
        raise PostgresError("Pool PostgreSQL belum siap")
    return _POOL


async def _acquire_conn():
    return await _pool().acquire()


async def _release_conn(conn) -> None:
    await _pool().release(conn)


async def _afetch(sql: str, *args: Any) -> List[Dict[str, Any]]:
    async with _pool().acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(row) for row in rows]


async def _afetchrow(sql: str, *args: Any) -> Optional[Dict[str, Any]]:
    async with _pool().acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row is not None else None


async def _afetchval(sql: str, *args: Any) -> Any:
    async with _pool().acquire() as conn:
        return await conn.fetchval(sql, *args)


async def _aexecute(sql: str, *args: Any) -> str:
    async with _pool().acquire() as conn:
        return await conn.execute(sql, *args)


async def _aexecutemany(sql: str, args_iterable: Sequence[Sequence[Any]]) -> None:
    async with _pool().acquire() as conn:
        await conn.executemany(sql, args_iterable)


def fetch(sql: str, *args: Any) -> List[Dict[str, Any]]:
    return _submit(_afetch(sql, *args))


def fetchrow(sql: str, *args: Any) -> Optional[Dict[str, Any]]:
    return _submit(_afetchrow(sql, *args))


def fetchval(sql: str, *args: Any) -> Any:
    return _submit(_afetchval(sql, *args))


def execute(sql: str, *args: Any) -> str:
    return _submit(_aexecute(sql, *args))


def executemany(sql: str, args_iterable: Sequence[Sequence[Any]]) -> None:
    _submit(_aexecutemany(sql, args_iterable))


class _TableQuery:
    __slots__ = (
        "_table",
        "_operation",
        "_columns",
        "_filters",
        "_orders",
        "_limit",
        "_payload",
    )

    def __init__(self, table: str) -> None:
        self._table = table
        self._operation = "select"
        self._columns = "*"
        self._filters: List[_Condition] = []
        self._orders: List[_Order] = []
        self._limit: Optional[int] = None
        self._payload: Any = None

    def select(self, columns: str = "*") -> "_TableQuery":
        self._operation = "select"
        self._columns = columns
        return self

    def insert(self, payload: Dict[str, Any] | List[Dict[str, Any]]) -> "_TableQuery":
        self._operation = "insert"
        self._payload = payload
        return self

    def update(self, payload: Dict[str, Any]) -> "_TableQuery":
        self._operation = "update"
        self._payload = payload
        return self

    def delete(self) -> "_TableQuery":
        self._operation = "delete"
        self._payload = None
        return self

    def eq(self, column: str, value: Any) -> "_TableQuery":
        from datetime import date

        if isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError:
                pass

        self._filters.append(_Condition("eq", column, value))
        return self
    def lte(self, column: str, value: Any) -> "_TableQuery":
        from datetime import date

        if isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError:
                pass

        self._filters.append(_Condition("lte", column, value))
        return self

    def order(self, column: str, desc: bool = False) -> "_TableQuery":
        self._orders.append(_Order(column=column, desc=desc))
        return self

    def limit(self, n: int) -> "_TableQuery":
        self._limit = int(n)
        return self

    def _compile_where(self, args: List[Any]) -> str:
        if not self._filters:
            return ""
        chunks: List[str] = []
        for cond in self._filters:
            args.append(cond.value)
            idx = len(args)
            col = _quote_ident(cond.column)
            if cond.op == "eq":
                chunks.append(f"{col} = ${idx}")
            elif cond.op == "lte":
                chunks.append(f"{col} <= ${idx}")
            else:
                raise PostgresError(f"Operator filter tidak didukung: {cond.op}")
        return " WHERE " + " AND ".join(chunks)

    def _compile_order(self) -> str:
        if not self._orders:
            return ""
        parts = []
        for order in self._orders:
            direction = "DESC" if order.desc else "ASC"
            parts.append(f"{_quote_ident(order.column)} {direction}")
        return " ORDER BY " + ", ".join(parts)

    def _compile_limit(self, args: List[Any]) -> str:
        if self._limit is None:
            return ""
        args.append(self._limit)
        return f" LIMIT ${len(args)}"

    def _compile_select(self) -> Tuple[str, List[Any]]:
        args: List[Any] = []
        where = self._compile_where(args)
        order = self._compile_order()
        limit = self._compile_limit(args)
        sql = f"SELECT {self._columns} FROM {_quote_ident(self._table)}{where}{order}{limit}"
        return sql, args

    def _compile_insert(self) -> Tuple[str, List[Any]]:
        if self._payload is None:
            raise PostgresError("Insert payload kosong")
        rows = self._payload if isinstance(self._payload, list) else [self._payload]
        if not rows:
            raise PostgresError("Insert payload kosong")

        columns = list(rows[0].keys())
        if any(list(r.keys()) != columns for r in rows):
            columns = sorted(set().union(*(r.keys() for r in rows)))

        args: List[Any] = []
        values_sql: List[str] = []
        for row in rows:
            placeholders: List[str] = []
            for col in columns:
                args.append(row.get(col))
                placeholders.append(f"${len(args)}")
            values_sql.append("(" + ", ".join(placeholders) + ")")

        cols_sql = ", ".join(_quote_ident(col) for col in columns)
        sql = f"INSERT INTO {_quote_ident(self._table)} ({cols_sql}) VALUES {', '.join(values_sql)} RETURNING *"
        return sql, args

    def _compile_update(self) -> Tuple[str, List[Any]]:
        if not isinstance(self._payload, dict) or not self._payload:
            raise PostgresError("Update payload kosong")
        args: List[Any] = []
        set_parts: List[str] = []
        for key, value in self._payload.items():
            args.append(value)
            set_parts.append(f"{_quote_ident(key)} = ${len(args)}")
        where = self._compile_where(args)
        sql = f"UPDATE {_quote_ident(self._table)} SET {', '.join(set_parts)}{where} RETURNING *"
        return sql, args

    def _compile_delete(self) -> Tuple[str, List[Any]]:
        args: List[Any] = []
        where = self._compile_where(args)
        sql = f"DELETE FROM {_quote_ident(self._table)}{where} RETURNING *"
        return sql, args

    def execute(self) -> QueryResponse:
        if self._operation == "select":
            sql, args = self._compile_select()
            return QueryResponse(fetch(sql, *args))
        if self._operation == "insert":
            sql, args = self._compile_insert()
            return QueryResponse(fetch(sql, *args))
        if self._operation == "update":
            sql, args = self._compile_update()
            return QueryResponse(fetch(sql, *args))
        if self._operation == "delete":
            sql, args = self._compile_delete()
            return QueryResponse(fetch(sql, *args))
        raise PostgresError(f"Operation tidak dikenal: {self._operation}")


class PostgresClient:
    def table(self, name: str) -> _TableQuery:
        return _TableQuery(name)


_CLIENT: PostgresClient | None = None


def get_postgres() -> PostgresClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = PostgresClient()
        try:
            init_pool()
        except Exception:
            pass
    return _CLIENT


class TransactionHandle:
    def __init__(self) -> None:
        self._conn = None
        self._tx = None

    def __enter__(self) -> "TransactionHandle":
        self._conn, self._tx = _submit(_acquire_transaction_pair())
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is None or self._tx is None:
            return
        try:
            if exc_type is None:
                _submit(self._tx.commit())
            else:
                _submit(self._tx.rollback())
        finally:
            _submit(_release_conn(self._conn))
            self._conn = None
            self._tx = None

    def fetch(self, sql: str, *args: Any) -> List[Dict[str, Any]]:
        if self._conn is None:
            raise PostgresError("Transaction belum aktif")
        return _submit(self._conn.fetch(sql, *args))

    def fetchrow(self, sql: str, *args: Any) -> Optional[Dict[str, Any]]:
        if self._conn is None:
            raise PostgresError("Transaction belum aktif")
        row = _submit(self._conn.fetchrow(sql, *args))
        return dict(row) if row is not None else None

    def fetchval(self, sql: str, *args: Any) -> Any:
        if self._conn is None:
            raise PostgresError("Transaction belum aktif")
        return _submit(self._conn.fetchval(sql, *args))

    def execute(self, sql: str, *args: Any) -> str:
        if self._conn is None:
            raise PostgresError("Transaction belum aktif")
        return _submit(self._conn.execute(sql, *args))


async def _acquire_transaction_pair():
    conn = await _pool().acquire()
    tx = conn.transaction()
    await tx.start()
    return conn, tx


@contextmanager
def transaction() -> Iterable[TransactionHandle]:
    tx = TransactionHandle()
    try:
        tx.__enter__()
        yield tx
        tx.__exit__(None, None, None)
    except Exception as exc:
        tx.__exit__(type(exc), exc, exc.__traceback__)
        raise


__all__ = [
    "PgConfig",
    "PostgresClient",
    "QueryResponse",
    "TransactionHandle",
    "close_pool",
    "execute",
    "executemany",
    "fetch",
    "fetchrow",
    "fetchval",
    "get_postgres",
    "init_pool",
    "transaction",
]
