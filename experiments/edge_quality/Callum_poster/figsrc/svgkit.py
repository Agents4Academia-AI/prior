"""Minimal SVG builder for the poster figures.

White background, Arial, Prior's palette. Same visual language as
`experiments/question_answering/trace.py` so the generated charts and the two
replayed trace figures read as one family on the sheet.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

# ── palette ──────────────────────────────────────────────────────────────────
INK = "#14181d"
DIM = "#6b7686"
FAINT = "#9aa4b0"
RULE = "#d9dee4"
PANEL = "#f5f7f9"
WHITE = "#ffffff"

# citation-intent axis (this work)
BG = "#8896a6"
UE = "#0a9396"
CC = "#bb3e03"

# semantic relations, the poster palette (see trace.py REL_COLOR). Darker and
# higher contrast than frontend/src/lib/colors.ts so they survive A0 print.
R_BUILDS = "#5b8fb0"
R_REFINES = "#ca6702"
R_CONTRA = "#ae2012"
R_SUPPORTS = "#0a9396"
R_CITES = "#000000"

# QA arms
ARM_GRAPH = "#0a9396"
ARM_WEB = "#bb3e03"
ARM_NULL = "#9aa4b0"

GOOD = "#2f9e44"
WARN = "#e8a33d"

FONT = "Arial, Helvetica, sans-serif"


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


class Fig:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.p: list[str] = []

    # ── primitives ───────────────────────────────────────────────────────────
    def rect(self, x, y, w, h, fill=WHITE, stroke=None, sw=1.5, rx=0, dash=None,
             op=None):
        a = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"'
        a += f' fill="{fill}"' if fill else ' fill="none"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if dash:
            a += f' stroke-dasharray="{dash}"'
        if op is not None:
            a += f' opacity="{op}"'
        self.p.append(a + "/>")

    def line(self, x1, y1, x2, y2, stroke=RULE, sw=1.5, dash=None, cap="round",
             marker=None, op=None):
        a = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"'
             f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"')
        if dash:
            a += f' stroke-dasharray="{dash}"'
        if marker:
            a += f' marker-end="url(#{marker})"'
        if op is not None:
            a += f' opacity="{op}"'
        self.p.append(a + "/>")

    def path(self, d, stroke=INK, sw=1.5, fill="none", dash=None, marker=None,
             op=None):
        a = f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"'
        if dash:
            a += f' stroke-dasharray="{dash}"'
        if marker:
            a += f' marker-end="url(#{marker})"'
        if op is not None:
            a += f' opacity="{op}"'
        self.p.append(a + "/>")

    def circle(self, cx, cy, r, fill=WHITE, stroke=None, sw=2, op=None):
        a = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"'
        a += f' fill="{fill}"' if fill else ' fill="none"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if op is not None:
            a += f' opacity="{op}"'
        self.p.append(a + "/>")

    def text(self, x, y, s, size=17, fill=INK, anchor="start", weight="normal",
             style="normal", spacing=None, op=None, halo=None):
        a = (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}"'
             f' font-size="{size}" fill="{fill}" text-anchor="{anchor}"')
        if weight != "normal":
            a += f' font-weight="{weight}"'
        if style != "normal":
            a += f' font-style="{style}"'
        if spacing:
            a += f' letter-spacing="{spacing}"'
        if op is not None:
            a += f' opacity="{op}"'
        if halo:
            a += (f' stroke="{halo}" stroke-width="6" stroke-linejoin="round"'
                  f' paint-order="stroke fill"')
        self.p.append(a + f">{esc(s)}</text>")

    # ── composites ───────────────────────────────────────────────────────────
    def title(self, x, y, s, size=30):
        self.text(x, y, s, size=size, weight="bold")

    def kicker(self, x, y, s, size=15, fill=DIM):
        self.text(x, y, s.upper(), size=size, fill=fill, weight="bold", spacing="1.6")

    def wrap(self, x, y, s, size=17, width=60, lh=1.42, fill=INK, anchor="start",
             weight="normal", style="normal"):
        """Naive word wrap at `width` characters. Returns the y after the block."""
        words, line, out = s.split(), "", []
        for w in words:
            t = (line + " " + w).strip()
            if len(t) > width and line:
                out.append(line)
                line = w
            else:
                line = t
        if line:
            out.append(line)
        for i, ln in enumerate(out):
            self.text(x, y + i * size * lh, ln, size=size, fill=fill,
                      anchor=anchor, weight=weight, style=style)
        return y + len(out) * size * lh

    def chip(self, x, y, s, fill, size=15, pad=10, h=26, text_fill=WHITE,
             weight="bold", rx=13):
        w = len(s) * size * 0.60 + pad * 2
        self.rect(x, y - h / 2, w, h, fill=fill, rx=rx)
        self.text(x + w / 2, y + size * 0.36, s, size=size, fill=text_fill,
                  anchor="middle", weight=weight)
        return w

    def marker_defs(self, colours):
        d = ["<defs>"]
        for name, col in colours.items():
            d.append(
                f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5"'
                f' markerWidth="4.4" markerHeight="4.4" orient="auto-start-reverse">'
                f'<path d="M 0 1 L 9.5 5 L 0 9 z" fill="{col}"/></marker>')
        d.append("</defs>")
        self.p.insert(0, "".join(d))

    # ── output ───────────────────────────────────────────────────────────────
    def save(self, path: Path):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}"'
                f' height="{self.h}" viewBox="0 0 {self.w} {self.h}"'
                f' font-family="{FONT}">\n'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="{WHITE}"/>\n')
        path.write_text(head + "\n".join(self.p) + "\n</svg>\n", encoding="utf-8")
        return path


# ── rasteriser (same approach as trace.py) ───────────────────────────────────
def to_png(svgs: list[Path], scale: int = 2) -> int:
    cand = [shutil.which("chrome"), shutil.which("msedge"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium"]
    exe = next((c for c in cand if c and Path(c).exists()), None)
    if not exe:
        print("no Chrome/Edge found - SVG only")
        return 0
    made = 0
    for svg in svgs:
        head = svg.read_text(encoding="utf-8")[:400]
        w = int(re.search(r'width="(\d+)"', head).group(1))
        h = int(re.search(r'height="(\d+)"', head).group(1))
        try:
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
                 f"--force-device-scale-factor={scale}",
                 "--default-background-color=FFFFFFFF",
                 f"--screenshot={svg.with_suffix('.png')}",
                 f"--window-size={w},{h}", svg.resolve().as_uri()],
                check=True, timeout=180,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            made += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ! {svg.name}: {e}")
    return made


# ── flattening a group transform ─────────────────────────────────────────────
# PowerPoint's "Convert to Shape" applies a <g transform="... scale(s)"> to
# coordinates but NOT to font-size, so every label inside the group comes back
# 1/s too large while anything outside it stays put. Baking the transform into
# the coordinates and deleting the group makes the file structurally identical
# to the ones we draw by hand, which convert cleanly.

_NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"

# attribute -> how it transforms: x position, y position, plain scale
_ATTRS = {
    "text":    {"x": "X", "y": "Y", "font-size": "S", "stroke-width": "S",
                "letter-spacing": "S"},
    "circle":  {"cx": "X", "cy": "Y", "r": "S", "stroke-width": "S"},
    "ellipse": {"cx": "X", "cy": "Y", "rx": "S", "ry": "S", "stroke-width": "S"},
    "line":    {"x1": "X", "y1": "Y", "x2": "X", "y2": "Y", "stroke-width": "S"},
    "rect":    {"x": "X", "y": "Y", "width": "S", "height": "S", "rx": "S",
                "ry": "S", "stroke-width": "S"},
    "path":    {"stroke-width": "S"},
}


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") or "0"


def _map_path_d(d: str, s: float, tx: float, ty: float) -> str:
    """Absolute M/L/Q/C/T/S only: every number after a command is an alternating
    x, y coordinate. Raises on anything else rather than silently mangling it."""
    tokens = re.findall(rf"[A-Za-z]|{_NUM}", d)
    bad = {t for t in tokens if t.isalpha()} - set("MLQCTS")
    if bad:
        raise ValueError(f"path command(s) {sorted(bad)} not handled by the flattener")
    out, is_x = [], True
    for t in tokens:
        if t.isalpha():
            out.append(t)
            is_x = True
        else:
            v = float(t)
            out.append(_fmt(v * s + (tx if is_x else ty)))
            is_x = not is_x
    return " ".join(out)


def flatten_group_transform(svg: str) -> str:
    """Bake a single `<g transform="translate(tx,ty) scale(s)">` into its
    children and remove the group. Returns the svg unchanged if there is none."""
    m = re.search(r'<g transform="translate\(({n}),({n})\)\s*scale\(({n})\)"\s*>'
                  .replace("{n}", _NUM), svg)
    if not m:
        return svg
    tx, ty, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
    close = svg.index("</g>", m.end())
    inner, head, tail = svg[m.end():close], svg[:m.start()], svg[close + 4:]
    if "<g " in inner:
        raise ValueError("nested groups are not handled by the flattener")

    def do_elem(em: re.Match) -> str:
        tag = em.group(1)
        body = em.group(2)
        rules = _ATTRS.get(tag)
        if rules is None:
            return em.group(0)

        def do_attr(am: re.Match) -> str:
            name, q, val = am.group(1), am.group(2), am.group(3)
            kind = rules.get(name)
            if kind == "X":
                val = _fmt(float(val) * s + tx)
            elif kind == "Y":
                val = _fmt(float(val) * s + ty)
            elif kind == "S":
                val = _fmt(float(val) * s)
            elif name == "stroke-dasharray":
                val = " ".join(_fmt(float(v) * s) for v in val.replace(",", " ").split())
            elif name == "d" and tag == "path":
                val = _map_path_d(val, s, tx, ty)
            else:
                return am.group(0)
            return f'{name}={q}{val}{q}'

        body = re.sub(r'([\w-]+)=(["\'])(.*?)\2', do_attr, body)
        return f"<{tag}{body}>"

    inner = re.sub(r"<(\w+)((?:\s+[\w-]+=(?:\"[^\"]*\"|'[^']*'))*\s*/?)>", do_elem, inner)
    return head + inner + tail
