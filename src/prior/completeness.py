"""How complete is the corpus? Two estimators, no third-party deps.

The honest answer to "have we missed papers?" is a number with a confidence
interval, not a cap. Two complementary tools:

1. capture_recapture  — the headline estimate for the corpus we have. Treat
   keyword/metadata SEARCH and the citation SNOWBALL as two independent samplers
   of the relevant literature. Their overlap pins down how much neither found:
   few papers seen by both ⇒ large unseen pool ⇒ low recall. (Lincoln–Petersen
   with Chapman's small-sample correction; Seber variance for the CI.)

2. buscar_pvalue / recall_reached — a hypergeometric stopping test in the spirit
   of Callaghan & Müller-Hansen (2020), "Statistical stopping criteria for
   automated screening in systematic reviews". For the ITERATIVE Scoper, where
   candidates are screened in descending predicted relevance: stop when we can
   reject, at confidence 1−alpha, the hypothesis that recall is still below the
   target. This is the principled replacement for "stop at top-k".
"""

from __future__ import annotations

import math


# ── 1. capture–recapture (search × snowball) ─────────────────────────────────
def capture_recapture(n_search: int, n_snowball: int, overlap: int) -> dict:
    """Estimate total relevant papers from two samplers.

    n_search   : relevant papers found by the search channel
    n_snowball : relevant papers reached by the citation channel
    overlap    : relevant papers found by BOTH (the recapture)
    """
    observed = n_search + n_snowball - overlap
    if overlap <= 0:
        return {"observed": observed, "estimate_total": None, "recall": None,
                "note": "no overlap between search and snowball — estimate "
                        "undefined; widen the snowball or add a sampler"}
    # Chapman-corrected Lincoln–Petersen (less biased for small overlap)
    n_hat = ((n_search + 1) * (n_snowball + 1) / (overlap + 1)) - 1
    var = ((n_search + 1) * (n_snowball + 1) * (n_search - overlap)
           * (n_snowball - overlap)) / (((overlap + 1) ** 2) * (overlap + 2))
    se = math.sqrt(var) if var > 0 else 0.0
    lo, hi = n_hat - 1.96 * se, n_hat + 1.96 * se
    return {
        "observed": observed,
        "estimate_total": round(n_hat, 1),
        "estimate_ci95": [round(max(observed, lo), 1), round(hi, 1)],
        "recall": round(observed / n_hat, 3) if n_hat > 0 else None,
        "recall_ci95": [round(observed / hi, 3) if hi > 0 else None,
                        round(min(1.0, observed / max(observed, lo)), 3)],
        "missing_estimate": round(max(0.0, n_hat - observed), 1),
        "overlap": overlap,
    }


# ── 2. Callaghan-style hypergeometric stopping test ──────────────────────────
def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _hypergeom_sf(k: int, N: int, K: int, n: int) -> float:
    """P(X >= k) for X ~ Hypergeometric(N population, K successes, n draws)."""
    lo = max(0, n - (N - K))
    hi = min(n, K)
    if k <= lo:
        return 1.0
    if k > hi:
        return 0.0
    denom = _log_choose(N, n)
    total = 0.0
    for x in range(k, hi + 1):
        total += math.exp(_log_choose(K, x) + _log_choose(N - K, n - x) - denom)
    return min(1.0, total)


def buscar_pvalue(relevant_found: int, screened: int, total: int,
                  recall_target: float = 0.95) -> float:
    """p-value for H0: recall < recall_target.

    Having screened `screened` of `total` candidates in descending predicted
    relevance and found `relevant_found` relevant, K0 = ceil(found / target) is
    the total number of relevant docs at which recall would sit exactly at the
    target. Under H0 those K0 are no more concentrated early than chance; a
    surprisingly high early yield (small p) is evidence the tail is depleted and
    the target is met. Reject H0 (stop) when p < alpha.
    """
    if relevant_found <= 0:
        return 1.0
    k0 = min(total, math.ceil(relevant_found / recall_target))
    return _hypergeom_sf(relevant_found, total, k0, screened)


def recall_reached(relevant_found: int, screened: int, total: int,
                   recall_target: float = 0.95, alpha: float = 0.05) -> bool:
    """True when we can stop: recall_target met at confidence 1 − alpha."""
    return buscar_pvalue(relevant_found, screened, total, recall_target) < alpha
