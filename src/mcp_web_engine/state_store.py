"""Local-host durable admission/telemetry. Never reads or writes credentials.

Every operation owns a connection; BEGIN IMMEDIATE serializes worker admissions.
Use a local filesystem shared by workers, not a distributed-host SQLite mount.
Admission totals and completed tool telemetry are deliberately separate counters.
"""
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class AdmissionDenied(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class StateUnavailable(Exception):
    """Storage failed; callers must fail closed without exposing paths/errors."""


def _state_dir():
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "mcp-web-engine"


def state_db_path():
    return Path(os.environ.get("MCP_WEB_ENGINE_STATE_DB") or _state_dir() / "usage.sqlite3")


def beta_keys_path():
    return Path(os.environ.get("MCP_WEB_ENGINE_BETA_KEYS_FILE") or _state_dir() / "beta_keys.json")


@contextmanager
def _connection(path=None):
    db = None
    try:
        target = Path(path) if path is not None else state_db_path()
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Create with private permissions without changing process-global umask.
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        db = sqlite3.connect(str(target), timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS usage (
            key_id TEXT PRIMARY KEY,
            window_started REAL NOT NULL DEFAULT 0,
            window_count INTEGER NOT NULL DEFAULT 0 CHECK(window_count >= 0),
            admissions INTEGER NOT NULL DEFAULT 0 CHECK(admissions >= 0),
            requests INTEGER NOT NULL DEFAULT 0 CHECK(requests >= 0),
            errors INTEGER NOT NULL DEFAULT 0 CHECK(errors >= 0),
            units INTEGER NOT NULL DEFAULT 0 CHECK(units >= 0),
            latency_total REAL NOT NULL DEFAULT 0,
            web_search INTEGER NOT NULL DEFAULT 0,
            fetch_url INTEGER NOT NULL DEFAULT 0,
            extract_markdown INTEGER NOT NULL DEFAULT 0,
            last_seen REAL
        )""")
        yield db
        db.commit()
    except (OSError, sqlite3.Error, OverflowError) as exc:
        if db is not None:
            db.rollback()
        raise StateUnavailable("Usage state unavailable") from exc
    finally:
        if db is not None:
            db.close()


def _ensure_row(db, key_id, capacity):
    if db.execute("SELECT 1 FROM usage WHERE key_id=?", (key_id,)).fetchone():
        return
    db.execute("INSERT INTO usage(key_id) VALUES (?)", (key_id,))


def admit(key_id, rate, *, quota=None, baseline=0, capacity=4096, now=None, path=None):
    """Atomically consume one HTTP admission or raise AdmissionDenied.

    Baseline imports legacy JSON requests via max(), never adding tool counts to
    admission quota. Wall-clock windows survive restart; clock rollback does not
    reset a live window. Operators must rotate tokens rather than delete DB rows.
    """
    now = time.time() if now is None else now
    with _connection(path) as db:
        _ensure_row(db, key_id, capacity)
        row = db.execute("SELECT * FROM usage WHERE key_id=?", (key_id,)).fetchone()
        used = max(row["admissions"], baseline)
        if quota is not None and used >= quota:
            raise AdmissionDenied("BETA_QUOTA_EXCEEDED")
        start, count = row["window_started"], row["window_count"]
        if count == 0 or now - start >= 60:
            start, count = now, 0
        # Capacity bounds live rate windows, not the lifetime quota ledger.
        # Historical admissions must remain durable even after a window expires.
        if row["window_count"] == 0 or now - row["window_started"] >= 60:
            live = db.execute(
                "SELECT COUNT(*) FROM usage WHERE window_count > 0 AND window_started > ?",
                (now - 60,),
            ).fetchone()[0]
            if live >= capacity:
                raise AdmissionDenied("RATE_LIMIT_CAPACITY")
        if count >= rate:
            raise AdmissionDenied("RATE_LIMIT_EXCEEDED")
        db.execute("UPDATE usage SET window_started=?, window_count=?, admissions=? WHERE key_id=?",
                   (start, count + 1, used + 1, key_id))


def read_usage(key_id=None, *, path=None) -> dict[str, Any]:
    """Return hashed-id counters, never credentials; None returns all rows."""
    with _connection(path) as db:
        if key_id is not None:
            row = db.execute("SELECT * FROM usage WHERE key_id=?", (key_id,)).fetchone()
            return dict(row) if row else {}
        return {row["key_id"]: dict(row) for row in db.execute("SELECT * FROM usage")}


def record_telemetry(key_id, tool_name, latency_ms, success, units=1, *, path=None):
    """Completed tool counters only; cannot authorize or restore a revoked key."""
    if not isinstance(latency_ms, (int, float)) or not math.isfinite(latency_ms) or latency_ms < 0:
        raise ValueError("Invalid latency")
    if type(units) is not int or units < 0:
        raise ValueError("Invalid units")
    with _connection(path) as db:
        _ensure_row(db, key_id, 4096)
        db.execute("""UPDATE usage SET requests=requests+1, errors=errors+?,
            units=units+?, latency_total=latency_total+?, last_seen=?,
            web_search=web_search+?, fetch_url=fetch_url+?, extract_markdown=extract_markdown+?
            WHERE key_id=?""",
            (int(not success), units, latency_ms, time.time(), int(tool_name == "web_search"),
             int(tool_name == "fetch_url"), int(tool_name == "extract_markdown"), key_id))
