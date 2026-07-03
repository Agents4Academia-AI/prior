# Prior — Frontend

Interactive React UI for **Prior**, a literature knowledge-graph system. It
visualises the cross-paper *contribution graph* and per-paper *claim graphs*,
and lets you ask the literature questions.

## Quick start

```bash
npm install
npm run dev
```

Then open the URL Vite prints (default http://localhost:5173).

The backend API must be running. By default the app calls
`http://127.0.0.1:8077`.

## Configuration

Set the API base URL with the `VITE_API_BASE` env var (no trailing slash
needed):

```bash
VITE_API_BASE=http://127.0.0.1:8077 npm run dev
```

Or create a `.env` file in this directory:

```
VITE_API_BASE=http://127.0.0.1:8077
```

## Build

```bash
npm run build      # type-checks then bundles to dist/
npm run preview    # serve the production build locally
```

## What's here

- **Left sidebar** — corpus stats (`/api/summary`) and the paper list
  (`/api/papers`). Click a paper to open its claim graph.
- **Main canvas** (React Flow) — toggle between:
  - **Global**: the contribution graph (`/api/graph/global`). Edges are
    coloured by relation; **solid = citation-backed**, **dashed = uncited
    parallel work** inferred from text. Click a node for its details.
  - **Local**: a selected paper's claim graph (`/api/graph/paper/{id}`), with
    claim nodes coloured by claim type and its contributions listed above.
- **Right panel** — tabbed:
  - **Details**: the selected contribution (problem/method/result + cite +
    global neighbours) or the selected claim.
  - **Ask**: ask a question (`/api/ask`, ~30s LLM call, shows a loading state)
    with a coloured verdict badge, plus "Trace origin" (`/api/origin`).

## Stack

Vite + React + TypeScript, [`@xyflow/react`](https://reactflow.dev) for graphs,
plain `fetch` for API calls. Graph layout is a small dependency-free
force-directed placement (`src/lib/layout.ts`).
