# Human annotation (verification → eval gold set)

Annotators verify the pipeline's output — **claims, contributions, and edges** —
to build the human gold set that grounds the eval (especially *relation accuracy*).
Everything lives in the same Neo4j graph; no extra store.

## Model

Annotations are nodes, keyed by what they judge — clean graph enrichment:
```
(:Annotation {id, annotator, target_kind, target_key, verdict, note, created_at})
  target_kind: claim | contribution | edge
  target_key:  node id, or "srcId|RELATION|dstId" for an edge
  verdict:     correct | incorrect | unsure        (+ edges: wrong_type / wrong_direction)
  id:          "<annotator>|<target_key>"           (one upsertable verdict per person per item)
```
No relationships — lookups are by the indexed `target_key`, and a whole subgraph's
tallies come back in **one batched query** (no N+1). `wipe()` spares annotations,
so a daemon re-ingest never loses human labels.

## Who can annotate / see what

Lightweight **username + token** (no real accounts) — enough for a demo you hand to
others, with independent per-person annotations.

- `data/users.json` maps `name -> {token, admin}` (copy `data/users.json.example`).
  **Real tokens are gitignored.**
- If `data/users.json` is absent, auth runs in **open dev mode**: any name, no token,
  non-admin (handy locally).
- The browser sends `X-Prior-User` / `X-Prior-Token` headers (set via the sign-in box).
- **Visibility:** you see only *your own* annotations, unless you're an **admin**
  (`admin: true`) or the global flag `PRIOR_ANNOTATIONS_SHARED=true` is set.

## Using it

1. Configure annotators: `cp data/users.json.example data/users.json` and edit.
2. `prior serve` + the UI; click **sign in** (name + token) in the sidebar.
3. Click any **node or edge** → the Details panel shows verdict buttons + a note.
   Saving upserts your verdict; the graph's inline tallies refresh.
4. Eval: the **Eval** tab shows human **edge/contribution/claim correctness** and
   **inter-annotator agreement**, computed live from annotations (also in `prior eval`).

## API

```
GET  /api/whoami
POST /api/annotate          {target_kind, target_key, verdict, note}
GET  /api/annotations?target_key=...
GET  /api/annotations/summary        # admin: cross-annotator agreement
```
All take the `X-Prior-User`/`X-Prior-Token` headers. The graph endpoints
(`/api/graph/global`, `/api/graph/paper/{id}`, `/api/contribution/{id}`) return each
node/edge's annotation tally inline when signed in.
