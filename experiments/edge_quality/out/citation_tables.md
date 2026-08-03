# Citation typing — results tables

Snapshot 2026-07-31. Evidence level **L0** (citee abstract + claim window), intra-corpus only.
All three axes now cover the **full working set: 809 claim-sites / 525 edges.**
Source files: `citations_typed.ckpt.json` (support + priority), `citations_intent.ckpt.json` (intent).

- **Site** = one `(edge, claim-context)` pair. **Edge** = one `(citing → cited)` pair (rolled up from its sites).
- Support/priority model = mixed (240 Opus + 569 Sonnet). Intent model = `claude-sonnet-5` (single).

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

## 3. Intent — `intent` (primary axis `t`)

**Site (n = 809)**

| intent | count | % |
|---|---:|---:|
| background | 665 | 82.2% |
| compares_contrasts | 89 | 11.0% |
| uses_extends | 55 | 6.8% |

**Edge (n = 525)** — rollup = strongest relation present (compares_contrasts > uses_extends > background)

| intent | count | % |
|---|---:|---:|
| background | 406 | 77.3% |
| compares_contrasts | 79 | 15.0% |
| uses_extends | 40 | 7.6% |

Mean confidence (intent pass): **0.74** · low-confidence (<0.6): 22 sites (2.7%) · unresolved/`unknown`: 0

---

## 4. Cross table — intent × support (site level, n = 809)

Counts:

| intent \ support | supports | partial | does_not | inconclusive | total |
|---|---:|---:|---:|---:|---:|
| background | 429 | 154 | 40 | 42 | 665 |
| uses_extends | 29 | 7 | 4 | 15 | 55 |
| compares_contrasts | 58 | 15 | 9 | 7 | 89 |
| **total** | **516** | **176** | **53** | **64** | **809** |

Row % (within each intent):

| intent \ support | supports | partial | does_not | inconclusive |
|---|---:|---:|---:|---:|
| background | 64.5% | 23.2% | 6.0% | 6.3% |
| uses_extends | 52.7% | 12.7% | 7.3% | 27.3% |
| compares_contrasts | 65.2% | 16.9% | 10.1% | 7.9% |

**Distrust rate** = share of an intent's sites the support axis marks `inconclusive` or `does_not`
(the abstract doesn't back the claim). uses_extends is ~3× background — L0 abstracts are the wrong
evidence for a methods-adoption citation, not a red flag:

| intent | distrust (inc + does_not) | rate |
|---|---:|---:|
| background | 82 / 665 | 12% |
| compares_contrasts | 16 / 89 | 18% |
| uses_extends | 19 / 55 | 35% |
