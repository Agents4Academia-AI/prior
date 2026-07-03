"""Navigator eval — citation validity.

Prior's whole pitch is grounding, so the load-bearing Navigator metric is: does
every id the answer cites actually exist in the atlas? Fabricated citations are
the failure mode we're trying to beat. The `validate` helper is key-free and
unit-tested; running it on a live answer needs an API key.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prior.atlas import Atlas  # noqa: E402

# Matches claim ids like [openalex:W123::c01] and paper ids like [arxiv:2401.00001].
_ID = re.compile(r"\[([a-zA-Z]+:[^\]\s]+)\]")


def cited_ids(text: str) -> list[str]:
    return _ID.findall(text or "")


def validate(atlas: Atlas, *texts: str) -> dict:
    known = set(atlas.claims) | set(atlas.papers)
    all_ids = [i for t in texts for i in cited_ids(t)]
    valid = [i for i in all_ids if i in known]
    invalid = sorted({i for i in all_ids if i not in known})
    return {
        "cited": len(all_ids),
        "valid": len(valid),
        "invalid_ids": invalid,
        "validity_rate": round(len(valid) / len(all_ids), 3) if all_ids else 1.0,
    }


if __name__ == "__main__":
    from prior import config, navigator  # noqa: E402

    if len(sys.argv) < 2:
        sys.exit('usage: python evals/citation_check.py "<question>"')
    atlas = Atlas.load(config.ATLAS / "atlas.json")
    ans = navigator.ask(atlas, sys.argv[1])
    texts = [ans.answer, *ans.supporting, *ans.contradicting, *ans.open_questions]
    r = validate(atlas, *texts)
    print("── Navigator eval (citation validity) ──")
    print(ans.render())
    print()
    print(f"citations: {r['valid']}/{r['cited']} valid  "
          f"(validity rate {r['validity_rate']:.1%})")
    if r["invalid_ids"]:
        print(f"FABRICATED ids: {r['invalid_ids']}")
