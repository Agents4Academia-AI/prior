"""Seed the Playwright browser profile with an authenticated Oxford session.

Run this ONCE, yourself, in your terminal (it opens a real browser window):

    pip install playwright && playwright install chromium
    PYTHONPATH=src python3 scripts/playwright_login.py

A browser opens at ACM. For each publisher you need (ACM, AAAS/Science, OUP,
Nature, PNAS): click "Sign in" -> "Access through your institution" -> search
"University of Oxford" -> authenticate at Oxford SSO (Shibboleth — Oxford is NOT
on OpenAthens). The first login establishes the Oxford IdP session, so the rest
are usually one click. Then press Enter here to save & close. The session persists
in PRIOR_PLAYWRIGHT_PROFILE and is reused by the Playwright fallback (PRIOR_PLAYWRIGHT=1).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prior import config   # noqa: E402

START = sys.argv[1] if len(sys.argv) > 1 else "https://dl.acm.org"


def main():
    from playwright.sync_api import sync_playwright
    print(f"profile dir : {config.PLAYWRIGHT_PROFILE}")
    print(f"opening     : {START}")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            config.PLAYWRIGHT_PROFILE, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(START)
        input("\nSign in via 'Access through your institution' -> University of Oxford at each "
              "publisher (ACM/Science/OUP/Nature/PNAS), then press Enter to save & close... ")
        ctx.close()
    print("session saved. Run the recovery with PRIOR_PLAYWRIGHT=1 to use it.")


if __name__ == "__main__":
    main()
