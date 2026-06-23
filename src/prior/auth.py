"""Lightweight username + token auth for the annotation feature.

Annotators identify with a name + passphrase token, checked against a configured
map (`users.json`: name -> {token, admin}). This keeps annotations independent
(one identity per annotator) and lets admins see everyone's work — enough for a
demo we hand to others, without a real account system.

If `users.json` is absent, auth runs in OPEN dev mode: any name is accepted with
no token, as a non-admin. Create the file to enforce tokens.

  users.json:
    { "alice": {"token": "s3cret", "admin": false},
      "harit": {"token": "boss",   "admin": true} }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from . import config


@dataclass
class Identity:
    user: str
    is_admin: bool
    open_mode: bool = False   # no users.json → unauthenticated dev mode


@lru_cache(maxsize=1)
def _users() -> dict:
    if config.USERS_FILE.exists():
        try:
            return json.loads(config.USERS_FILE.read_text())
        except (ValueError, OSError):
            return {}
    return {}


def reload_users() -> None:
    _users.cache_clear()


def authenticate(user: Optional[str], password: Optional[str]) -> Optional[Identity]:
    """Return an Identity if (user, password) is valid, else None.
    In open mode (no users.json) any non-empty user is accepted as a non-admin."""
    user = (user or "").strip()
    if not user:
        return None
    users = _users()
    if not users:                                   # open dev mode
        return Identity(user=user, is_admin=False, open_mode=True)
    rec = users.get(user)
    if not rec or rec.get("password") != (password or ""):
        return None
    return Identity(user=user, is_admin=bool(rec.get("admin")))


def can_see_others(ident: Identity) -> bool:
    """Whether this identity may view other annotators' annotations."""
    return ident.is_admin or config.ANNOTATIONS_SHARED
