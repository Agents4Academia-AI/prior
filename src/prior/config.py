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
# Institutional access (e.g. Oxford / Bodleian) for paywalled papers the user is
# *entitled* to. OFF unless an EZproxy host is set. Auth is supplied as a Netscape
# cookie file exported from a logged-in browser session (we never handle creds).
# Prefer Crossref TDM links (sanctioned for mining) over scraping landing pages.
EZPROXY_HOST = os.environ.get("PRIOR_EZPROXY_HOST", "")            # e.g. ezproxy.ox.ac.uk
INSTITUTIONAL_COOKIES = os.environ.get("PRIOR_INSTITUTIONAL_COOKIES", "")  # path to cookies.txt
# Elsevier ScienceDirect full-text API (the sanctioned TDM route for ~Elsevier
# papers). Key + optional institutional token; entitlement also honours IP range.
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
# Politeness: delay (seconds) between publisher/institutional fetches, and a cap.
FULLTEXT_DELAY = float(os.environ.get("PRIOR_FULLTEXT_DELAY", "2.0"))
# Playwright fallback for website-only publishers — drives a real browser.
# POLICY: per the Bodleian (TDM guide), automated *bulk* browser downloading of
# subscription e-resources is NOT permitted; the sanctioned bulk route is
# individual publisher APIs. Keep this OFF for bulk runs; use only for occasional,
# permitted, human-paced single fetches you are entitled to. Opt-in (heavy dep);
# reuses a persistent SSO profile (seed it: scripts/playwright_login.py).
PLAYWRIGHT = os.environ.get("PRIOR_PLAYWRIGHT", "").lower() in ("1", "true", "yes")
PLAYWRIGHT_PROFILE = os.environ.get("PRIOR_PLAYWRIGHT_PROFILE",
                                    str(Path.home() / ".prior_browser_profile"))

# ── Pipeline knobs ──────────────────────────────────────────────────────────────
DEFAULT_MAX_PAPERS = int(os.environ.get("PRIOR_MAX_PAPERS", "25"))
# How many other-paper claims to consider as relation candidates per claim.
RELATION_NEIGHBORS = int(os.environ.get("PRIOR_RELATION_NEIGHBORS", "6"))
# Max chars of full text fed to the Reader (head+tail window when longer).
FULLTEXT_CHARS = int(os.environ.get("PRIOR_FULLTEXT_CHARS", "48000"))


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    ATLAS.mkdir(parents=True, exist_ok=True)
    FULLTEXT.mkdir(parents=True, exist_ok=True)
