# PRIOR — AIASci 2026

Frozen workshop presentation: **Inspectable contribution maps for scientific synthesis**.

[View the animated slides](https://prior-aiasci-2026.kaleb-klara97257971.chatgpt.site/) · [Download the PDF](https://prior-aiasci-2026.kaleb-klara97257971.chatgpt.site/PRIOR-AIASci-2026.pdf)

Ten main slides and one backup. Use the arrow keys or Space to advance through reveals; F enters full screen. The publication timeline has a Replay button. The graph animations use the retained corpus; they do not reconstruct when relationships were discovered.

## Offline use

Download `PRIOR.html` and open it in a browser. All slide assets are embedded. Keep `PRIOR-AIASci-2026.pdf` beside it if you want the PDF button to work offline. Paper and website links require internet.

## Editable source

`index.html`, `deck.css`, `deck.js`, `graph-data.js` and `assets/` are the source. Rebuild with:

```sh
python3 talks/aiasci-2026/build.py
```

To regenerate the PDF, install Playwright outside the repository and run `export_pdf.cjs` with a Chrome executable path. This static presentation does not use the PRIOR Python runtime.

The public snapshot excludes speaker notes, private research notes, QA screenshots and unused assets. Provenance is recorded in `provenance.json`. `SHA256SUMS` identifies the frozen HTML and PDF. Preserve this edition; publish substantive later revisions as a new edition.

## Attribution

Authors: Klara Kaleb, Harit Vishwakarma, Callum Young, Yee Whye Teh.

Presented at AIASci 2026 — End-to-End Research Workflow, Methods, and Applications for AI-Assisted Science, San Francisco, USA.

PRIOR originated in the Agents4Academia Oxford–Singapore Hackathon. Institutional logos are acknowledgements and remain the property of their respective owners. The repo's code license and graph-data attribution apply; logos are not relicensed.
