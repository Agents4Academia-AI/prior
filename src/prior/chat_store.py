"""Durable, server-side chat storage (SQLite).

Chats are owned by a user, so a conversation can be retrieved from any browser or
device, and survives the client losing its localStorage. This is the source of
truth; the frontend just renders what the server returns.

Stored separately from the Neo4j knowledge graph, in `data/chats.db`:
  sessions(id, user, title, created_at, updated_at)
  messages(id, session_id, user, role, content, trace, created_at)

`trace` is the JSON tool-call record for an assistant turn (which searches ran,
result counts, ReAct thoughts), kept so a reloaded chat still shows "graph queries".
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from . import config

_DB = config.DATA / "chats.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@contextmanager
def _conn():
    config.DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")        # durable + concurrent reads
        c.execute("PRAGMA foreign_keys=ON")
        _init(c)
        yield c
        c.commit()
    finally:
        c.close()


def _init(c: sqlite3.Connection) -> None:
    c.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        "  id TEXT PRIMARY KEY, user TEXT NOT NULL, title TEXT,"
        "  created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,"
        "  user TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,"
        "  trace TEXT, created_at TEXT NOT NULL)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user, updated_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id, id)")


def _norm_user(user: Optional[str]) -> str:
    """All chats are owned by someone; unauthenticated/open-mode callers get a
    stable 'anon' bucket so their history still persists across reloads."""
    return (user or "").strip() or "anon"


# ── sessions ──────────────────────────────────────────────────────────────────
def create_session(user: Optional[str], title: Optional[str] = None,
                    sid: Optional[str] = None) -> dict:
    user = _norm_user(user)
    sid = sid or _new_id()
    now = _now()
    with _conn() as c:
        # If the client supplied an id that already exists for someone else, mint a new one.
        row = c.execute("SELECT user FROM sessions WHERE id=?", (sid,)).fetchone()
        if row and row["user"] != user:
            sid = _new_id()
        c.execute(
            "INSERT OR IGNORE INTO sessions(id, user, title, created_at, updated_at) "
            "VALUES(?,?,?,?,?)", (sid, user, title or "New chat", now, now))
    return {"id": sid, "user": user, "title": title or "New chat",
            "created_at": now, "updated_at": now}


def list_sessions(user: Optional[str], limit: int = 200) -> list[dict]:
    user = _norm_user(user)
    with _conn() as c:
        rows = c.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "  (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS n "
            "FROM sessions s WHERE s.user=? ORDER BY s.updated_at DESC LIMIT ?",
            (user, int(limit))).fetchall()
    return [dict(r) for r in rows]


def get_session(user: Optional[str], sid: str) -> Optional[dict]:
    user = _norm_user(user)
    with _conn() as c:
        s = c.execute("SELECT id, title, created_at, updated_at FROM sessions "
                      "WHERE id=? AND user=?", (sid, user)).fetchone()
        if not s:
            return None
        msgs = c.execute(
            "SELECT role, content, trace, created_at FROM messages "
            "WHERE session_id=? ORDER BY id", (sid,)).fetchall()
    return {**dict(s), "messages": [_msg_row(m) for m in msgs]}


def _msg_row(m: sqlite3.Row) -> dict:
    out = {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
    if m["trace"]:
        try:
            out["trace"] = json.loads(m["trace"])
        except ValueError:
            pass
    return out


def rename_session(user: Optional[str], sid: str, title: str) -> bool:
    user = _norm_user(user)
    with _conn() as c:
        cur = c.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=? AND user=?",
                        (title.strip()[:120] or "New chat", _now(), sid, user))
        return cur.rowcount > 0


def delete_session(user: Optional[str], sid: str) -> bool:
    user = _norm_user(user)
    with _conn() as c:
        cur = c.execute("DELETE FROM sessions WHERE id=? AND user=?", (sid, user))
        return cur.rowcount > 0


# ── messages ──────────────────────────────────────────────────────────────────
def add_message(user: Optional[str], sid: str, role: str, content: str,
                trace: Optional[list] = None) -> None:
    """Append one turn and bump the session's updated_at. Creates the session if
    it does not exist yet (first turn of a brand-new chat)."""
    user = _norm_user(user)
    now = _now()
    with _conn() as c:
        s = c.execute("SELECT id FROM sessions WHERE id=? AND user=?", (sid, user)).fetchone()
        if not s:
            title = content.strip()[:60] if role == "user" else "New chat"
            c.execute("INSERT OR IGNORE INTO sessions(id, user, title, created_at, updated_at) "
                      "VALUES(?,?,?,?,?)", (sid, user, title, now, now))
        c.execute(
            "INSERT INTO messages(session_id, user, role, content, trace, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (sid, user, role, content, json.dumps(trace) if trace else None, now))
        # First user turn names an untitled chat.
        if role == "user":
            c.execute("UPDATE sessions SET title=CASE WHEN title IN ('New chat','') "
                      "THEN ? ELSE title END, updated_at=? WHERE id=?",
                      (content.strip()[:60] or "New chat", now, sid))
        else:
            c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, sid))


def history(user: Optional[str], sid: str) -> list[dict]:
    """Stored conversation as [{role, content}] for feeding back to the model."""
    sess = get_session(user, sid)
    if not sess:
        return []
    return [{"role": m["role"], "content": m["content"]} for m in sess["messages"]]
