"""Central configuration. Override via environment variables."""

import os
from pathlib import Path

# ── Models ────────────────────────────────────────────────────────────────────
# Extraction/mapping is high-volume → a fast, cheap model. Navigation is the
# user-facing reasoning step → allow a stronger model.
READER_MODEL = os.environ.get("PRIOR_READER_MODEL", "claude-sonnet-4-6")
CARTOGRAPHER_MODEL = os.environ.get("PRIOR_CARTOGRAPHER_MODEL", "claude-sonnet-4-6")
NAVIGATOR_MODEL = os.environ.get("PRIOR_NAVIGATOR_MODEL", "claude-opus-4-8")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("PRIOR_DATA_DIR", ROOT / "data"))
RAW = DATA / "raw"        # cached source responses (papers)
ATLAS = DATA / "atlas"    # built atlas (claims + graph)

# ── Source / network ────────────────────────────────────────────────────────────
# OpenAlex asks for a contact email in the "polite pool" for faster, reliable
# access. Falls back to a generic UA if unset.
CONTACT_EMAIL = os.environ.get("PRIOR_CONTACT_EMAIL", "")
USER_AGENT = f"prior/0.1 (https://github.com/agents4academia; mailto:{CONTACT_EMAIL})"
HTTP_TIMEOUT = int(os.environ.get("PRIOR_HTTP_TIMEOUT", "30"))

# ── Pipeline knobs ──────────────────────────────────────────────────────────────
DEFAULT_MAX_PAPERS = int(os.environ.get("PRIOR_MAX_PAPERS", "25"))
# How many other-paper claims to consider as relation candidates per claim.
RELATION_NEIGHBORS = int(os.environ.get("PRIOR_RELATION_NEIGHBORS", "6"))
# Max chars of full text fed to the Reader (head+tail window when longer).
FULLTEXT_CHARS = int(os.environ.get("PRIOR_FULLTEXT_CHARS", "48000"))

# ── Annotation / auth ───────────────────────────────────────────────────────────
# users.json maps username -> {"token": "...", "admin": true|false}. When the file
# is absent, auth runs in OPEN dev mode (any name, no token, non-admin).
USERS_FILE = Path(os.environ.get("PRIOR_USERS_FILE", str(DATA / "users.json")))
# When true, every annotator can see everyone's annotations (else only their own).
ANNOTATIONS_SHARED = os.environ.get("PRIOR_ANNOTATIONS_SHARED", "").lower() in ("1", "true", "yes")
ANNOTATIONS_DB = DATA / "annotations.db"


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    ATLAS.mkdir(parents=True, exist_ok=True)
