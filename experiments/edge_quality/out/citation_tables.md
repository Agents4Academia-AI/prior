# Citation typing — results tables

Snapshot 2026-07-30. Evidence level **L0** (citee abstract + claim window), intra-corpus only.
Source files: `citations_typed.ckpt.json` (support + priority, all 809 sites / 525 edges),
`citations_intent.ckpt.json` (intent, 280 sites / 186 edges — partial run).

- **Site** = one `(edge, claim-context)` pair. **Edge** = one `(citing → cited)` pair (rolled up from its sites).

---

## 1. Support — `supports_claim`

**Site (n = 809)**

| verdict | count | % |
|---|---:|---:|
| supports | 516 | 63.8% |
| partial | 176 | 21.8% |
| inconclusive | 64 | 7.9% |
| does_not | 53 | 6.6% |

**Edge (n = 525)** — rollup = strongest support present

| verdict | count | % |
|---|---:|---:|
| supports | 382 | 72.8% |
| partial | 86 | 16.4% |
| does_not | 30 | 5.7% |
| inconclusive | 27 | 5.1% |

Mean confidence (support/priority pass): **0.69**

---

## 2. Priority — `priority`

**Site (n = 809)**

| priority | count | % |
|---|---:|---:|
| obligatory | 423 | 52.3% |
| helpful | 386 | 47.7% |

**Edge (n = 525)** — rollup = obligatory if any site is obligatory

| priority | count | % |
|---|---:|---:|
| obligatory | 312 | 59.4% |
| helpful | 213 | 40.6% |

---

## 3. Intent — `intent` (primary axis `t`, partial run)

**Site (n = 280)**

| intent | count | % |
|---|---:|---:|
| background | 225 | 80.4% |
| compares_contrasts | 37 | 13.2% |
| uses_extends | 18 | 6.4% |

**Edge (n = 186)** — rollup = strongest relation present (compares_contrasts > uses_extends > background)

| intent | count | % |
|---|---:|---:|
| background | 137 | 73.7% |
| compares_contrasts | 34 | 18.3% |
| uses_extends | 15 | 8.1% |

Mean confidence (intent pass): **0.73**

---

## 4. Cross table — intent × support (site level, n = 280)

Counts:

| intent \ support | supports | partial | does_not | inconclusive | total |
|---|---:|---:|---:|---:|---:|
| background | 166 | 46 | 7 | 6 | 225 |
| uses_extends | 11 | 3 | 2 | 2 | 18 |
| compares_contrasts | 28 | 6 | 2 | 1 | 37 |
| **total** | **205** | **55** | **11** | **9** | **280** |

Row % (within each intent):

| intent \ support | supports | partial | does_not | inconclusive |
|---|---:|---:|---:|---:|
| background | 73.8% | 20.4% | 3.1% | 2.7% |
| uses_extends | 61.1% | 16.7% | 11.1% | 11.1% |
| compares_contrasts | 75.7% | 16.2% | 5.4% | 2.7% |
