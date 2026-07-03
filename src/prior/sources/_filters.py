"""Source-level filters (shared by adapters; no package-level imports)."""

import re

_REVIEW_TITLE = re.compile(
    r"(?i)\bsurvey\b|\bsystematic review\b|\b(a|comprehensive) review\b|"
    r"\breview of\b|:\s*a review\b|\boverview of\b")


def looks_like_review(title: str, work_type: str = "") -> bool:
    """Heuristic: is this a review/survey rather than primary research?
    Uses OpenAlex `type` when available, plus strong title signals."""
    if (work_type or "").lower() == "review":
        return True
    return bool(_REVIEW_TITLE.search(title or ""))
