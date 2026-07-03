"""Central configuration. Override via environment variables."""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load a local, gitignored .env so secrets (e.g. PRIOR_S2_API_KEY) apply to
    every run without re-exporting. Real environment variables take precedence."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]                       # strip surrounding quotes (dotenv-style)
        os.environ.setdefault(k.strip(), v)


_load_dotenv()

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
FULLTEXT = DATA / "fulltext"   # cached raw full texts (provenance; re-extract source)
FULLPAPER = DATA / "fullpaper"  # rich Markdown renders (LaTeX math + embedded images)

# ── Source / network ────────────────────────────────────────────────────────────
# OpenAlex asks for a contact email in the "polite pool" for faster, reliable
# access. Falls back to a generic UA if unset.
CONTACT_EMAIL = os.environ.get("PRIOR_CONTACT_EMAIL", "")
USER_AGENT = f"prior/0.1 (https://github.com/agents4academia; mailto:{CONTACT_EMAIL})"
HTTP_TIMEOUT = int(os.environ.get("PRIOR_HTTP_TIMEOUT", "30"))

# ── Full-text retrieval ─────────────────────────────────────────────────────────
# Unpaywall finds a *legal* open-access copy by DOI (green/gold OA that OpenAlex's
# best_oa_location often misses). Free; just needs a contact email.
UNPAYWALL_EMAIL = os.environ.get("PRIOR_UNPAYWALL_EMAIL",
                                 os.environ.get("UNPAYWALL_EMAIL", CONTACT_EMAIL))
# Publisher text-mining APIs — the sanctioned TDM route for entitled readers.
# Bring your own keys if you have them; all optional and OFF unless set. Elsevier
# ScienceDirect first: key + optional institutional token (also honours IP range).
def _key(*names: str, default: str = "") -> str:
    """First non-empty env var among `names` — lets us accept both PRIOR_-prefixed
    names and the bare names used by the nbs-data-hunter .env, so the same keys
    work in both projects."""
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return default


ELSEVIER_API_KEY = _key("PRIOR_ELSEVIER_API_KEY", "ELSEVIER_API_KEY")
ELSEVIER_INSTTOKEN = _key("PRIOR_ELSEVIER_INSTTOKEN", "ELSEVIER_INSTTOKEN")
SPRINGER_API_KEY = _key("PRIOR_SPRINGER_API_KEY", "SPRINGER_API_KEY")
WILEY_API_KEY = _key("PRIOR_WILEY_API_KEY", "WILEY_API_KEY")
# Politeness: delay (seconds) between publisher API fetches.
FULLTEXT_DELAY = float(os.environ.get("PRIOR_FULLTEXT_DELAY", "2.0"))

# ── Pipeline knobs ──────────────────────────────────────────────────────────────
DEFAULT_MAX_PAPERS = int(os.environ.get("PRIOR_MAX_PAPERS", "25"))
# How many other-paper claims to consider as relation candidates per claim.
RELATION_NEIGHBORS = int(os.environ.get("PRIOR_RELATION_NEIGHBORS", "6"))
# Max chars of full text fed to the Reader (head+tail window when longer).
FULLTEXT_CHARS = int(os.environ.get("PRIOR_FULLTEXT_CHARS", "48000"))

# ── fullpaper: rich Markdown render (LaTeX math + embedded figures) ───────────────
# Defaults for the standalone "fullpaper" stage; each is also a per-call/CLI knob.
def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.lower() in ("1", "true", "yes")


FULLPAPER_MATH = _flag("PRIOR_FULLPAPER_MATH", True)        # keep equations as LaTeX
FULLPAPER_IMAGES = _flag("PRIOR_FULLPAPER_IMAGES", True)    # include figures/plots
FULLPAPER_EMBED_IMAGES = _flag("PRIOR_FULLPAPER_EMBED", True)  # base64-inline vs assets dir
# Page cap for the PDF fallback (0 = all). The arXiv-HTML path is not paginated and
# is always rendered in full.
FULLPAPER_MAX_PAGES = int(os.environ.get("PRIOR_FULLPAPER_MAX_PAGES", "0"))
# Drop raster images smaller than this (px, either side) — icons, rules, logos.
FULLPAPER_MIN_IMAGE_PX = int(os.environ.get("PRIOR_FULLPAPER_MIN_IMAGE_PX", "50"))

# ── Annotation / auth ───────────────────────────────────────────────────────────
# users.json maps username -> {"token": "...", "admin": true|false}. When the file
# is absent, auth runs in OPEN dev mode (any name, no token, non-admin).
USERS_FILE = Path(os.environ.get("PRIOR_USERS_FILE", str(DATA / "users.json")))
# Default collection the UI opens to (a named corpus in the graph).
DEFAULT_COLLECTION = os.environ.get("PRIOR_DEFAULT_COLLECTION", "core-v0.2")
# When true, every annotator can see everyone's annotations (else only their own).
ANNOTATIONS_SHARED = os.environ.get("PRIOR_ANNOTATIONS_SHARED", "").lower() in ("1", "true", "yes")
ANNOTATIONS_DB = DATA / "annotations.db"


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    ATLAS.mkdir(parents=True, exist_ok=True)
    FULLTEXT.mkdir(parents=True, exist_ok=True)
    FULLPAPER.mkdir(parents=True, exist_ok=True)
