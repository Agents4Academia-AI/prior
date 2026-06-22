"""Auth tests — no Neo4j / no API key (open mode + token map)."""
import json

from prior import auth, config


def test_open_mode_when_no_users_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USERS_FILE", tmp_path / "nope.json")
    auth.reload_users()
    ident = auth.authenticate("alice", "")
    assert ident and ident.user == "alice" and ident.open_mode and not ident.is_admin
    assert auth.authenticate("", "") is None       # empty name rejected


def test_token_enforced_with_users_file(tmp_path, monkeypatch):
    f = tmp_path / "users.json"
    f.write_text(json.dumps({"alice": {"token": "s3cret", "admin": False},
                             "boss": {"token": "k", "admin": True}}))
    monkeypatch.setattr(config, "USERS_FILE", f)
    auth.reload_users()
    assert auth.authenticate("alice", "s3cret").is_admin is False
    assert auth.authenticate("alice", "wrong") is None      # bad token
    assert auth.authenticate("ghost", "x") is None          # unknown user
    assert auth.authenticate("boss", "k").is_admin is True
    auth.reload_users()  # reset cache for other tests


def test_can_see_others(monkeypatch):
    admin = auth.Identity(user="boss", is_admin=True)
    plain = auth.Identity(user="alice", is_admin=False)
    monkeypatch.setattr(config, "ANNOTATIONS_SHARED", False)
    assert auth.can_see_others(admin) is True
    assert auth.can_see_others(plain) is False
    monkeypatch.setattr(config, "ANNOTATIONS_SHARED", True)
    assert auth.can_see_others(plain) is True
