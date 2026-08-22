# v1 run — ARCHIVED, NOT VALID FOR SCORING

Two questions (q01, q02) x three arms, run 2026-08-20. Retained as evidence, not as
results. Two independent problems invalidate them for scoring:

1. **The arms were not sealed.** `ClaudeAgentOptions.allowed_tools` is a PERMISSION
   allowlist, not a tool-surface restriction — that is the separate `tools=` field,
   which v1 never set. With `permission_mode="bypassPermissions"` every default
   Claude Code tool was live in every arm. Observed consequence: the q02 GRAPH run
   opened with `Skill(prior)` and `Bash(python -m prior.cli info)`, i.e. it consulted
   the repo's own Prior skill and shell. The NULL arm had WebSearch available
   throughout; it did not call it, so it was closed-book by luck, not by construction.

2. **The graph tool surface was contribution-level while every question is
   paper-level**, so the graph arm spent turns reassembling paper-level facts that
   the atlas already holds. See ../TOOL_SURFACE_V2.md.

## What v1 is still good for

The per-arm token accounting is real and is the baseline for the efficiency claim
(same questions, same model, same judge — only the tool surface changed):

| run | turns | new tokens into context | tool calls | payload chars |
|---|---|---|---|---|
| q01 graph | 19 | 43,443 | 15 | 59,374 |
| q01 web   |  9 | 25,366 |  4 | — |
| q01 null  |  4 | 16,577 |  0 | — |
| q02 graph | 16 | 40,010 |  9 (+3 out-of-arm) | 39,059 |
| q02 web   |  6 | 19,396 |  2 | — |
| q02 null  |  6 | 20,648 |  0 | — |

Cost per turn was LOWER for graph ($0.026-0.028) than web ($0.046) or null ($0.051);
the graph arm was more expensive purely because it took 2-3x more turns.
