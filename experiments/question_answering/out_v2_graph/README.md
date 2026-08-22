# v2 graph rows — superseded by v3, retained for the tool-surface comparison

Five GRAPH-arm answers generated 2026-08-20/21 against the **v2** tool surface
(`paper_neighbourhood` returning full JSON-object list rows, abstracts, and a
320-char justification stub on every edge whether asked for or not).

They are **not** invalid — the arm was sealed, `off_arm_tools` was empty on all
five, leakage was clean and all 43 named papers resolved to the corpus. They are
superseded because the tool surface changed underneath them, so they are no
longer comparable with the v3 graph rows.

Kept because the whole point of the v3 change is the comparison: **same graph,
same questions, same model — how much text did each interface need?**

| q   | tokens_in | payload | calls | turns |
|-----|----------:|--------:|------:|------:|
| q01 |    32,019 |  47,843 |     5 |    10 |
| q02 |    13,969 |  14,787 |     2 |     4 |
| q03 |    35,915 |  69,748 |     8 |    11 |
| q04 |    22,803 |  41,762 |     5 |     7 |
| q05 |    26,072 |  48,567 |     9 |    11 |

The web and null rows for q01–q04 were **not** archived and remain live in
`out/answers.jsonl` — nothing about those two arms changed, so re-running them
would only cost money and add noise.

The v2 payloads are reproducible byte-for-byte at zero cost:
`atlas.paper_neighbourhood(pid, verbose=True)` and
`atlas.topic_structure(q, verbose=True)` still return the v2 shape.
