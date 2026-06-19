"""Drive the interactive Claude Code CLI on a subscription — no API credits.

Why this exists
---------------
The headless `-p/--print` path (and the Agent SDK, which wraps it) now meter
against API credits even on a Max plan. Only the *interactive* TUI runs on the
Claude Code login. So to spend nothing we drive the interactive session through
a pseudo-terminal (PTY).

The interactive TUI is redraw-heavy and painful to scrape, so we don't. Instead:

    file in  -> we write the full prompt (system + schema + task) to an input file
    one line -> we tell Claude: read that file, write your JSON to an output file
    file out -> we read + parse the output file

The typed message is a single short line (no embedded newlines, which the TUI
would treat as "submit"), and the answer never has to survive the screen.

`--dangerously-skip-permissions` is used so Claude can Read/Write those temp
files without an interactive permission prompt. This is safe here: we control
the prompt, and the only tools needed are file read/write in a temp dir.
"""

from __future__ import annotations

import itertools
import json
import os
import tempfile
import time
from typing import Any, Optional

import pexpect

from .llm import extract_json  # reuse the lenient JSON parser

_counter = itertools.count()
_SPAWN_CMD = "claude"
_SPAWN_ARGS = ["--ax-screen-reader", "--dangerously-skip-permissions"]

# Where Claude is launched. CLAUDE.md auto-discovery etc. is harmless here.
_CWD = str(__import__("pathlib").Path(__file__).resolve().parents[2])


def _tmp(tag: str, ext: str) -> str:
    pid, n = os.getpid(), next(_counter)
    return os.path.join(tempfile.gettempdir(), f"prior_{tag}_{pid}_{n}.{ext}")


def run_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    timeout: int = 240,
    startup_timeout: int = 30,
) -> dict[str, Any]:
    """Run one extraction turn through the interactive CLI and return a dict
    matching `schema`. Raises on timeout / unparseable output."""
    infile = _tmp("in", "txt")
    outfile = _tmp("out", "json")
    for f in (infile, outfile):
        if os.path.exists(f):
            os.remove(f)

    prompt_doc = (
        f"{system}\n\n"
        "=== TASK ===\n"
        f"{user}\n\n"
        "=== OUTPUT ===\n"
        "Respond by writing a SINGLE JSON object that conforms to this JSON "
        "Schema to the output file (see the message). Write nothing else to the "
        "file: no prose, no markdown fences.\n"
        f"JSON Schema:\n{json.dumps(schema, indent=2)}\n"
    )
    with open(infile, "w") as fh:
        fh.write(prompt_doc)

    child = pexpect.spawn(
        _SPAWN_CMD, _SPAWN_ARGS, encoding="utf-8",
        timeout=timeout, dimensions=(50, 220), cwd=_CWD,
    )
    try:
        # One-time per-directory trust gate, if it appears.
        i = child.expect([r"Enter y/n", r"Welcome", pexpect.TIMEOUT],
                         timeout=startup_timeout)
        if i == 0:
            child.send("y")
            child.send("\r")
            time.sleep(2)
        time.sleep(1.5)

        msg = (
            f"Read the file {infile} and follow its instructions exactly. "
            f"Write your JSON answer to {outfile} using the Write tool. "
            f"Do not print the JSON in your reply."
        )
        child.send(msg)
        time.sleep(0.5)
        child.send("\r")

        text = _poll_text(outfile, timeout=timeout)
        if text is not None:
            # extract_json tolerates ```json fences / trailing prose in the file.
            return extract_json(text)

        # Fallback: model printed instead of writing — try to scrape the screen.
        raw = (child.before or "") + _drain(child)
        return extract_json(raw)
    finally:
        try:
            child.sendcontrol("c"); time.sleep(0.2); child.sendcontrol("c")
            child.expect(pexpect.EOF, timeout=5)
        except Exception:
            child.close(force=True)
        for f in (infile, outfile):
            try:
                os.remove(f)
            except OSError:
                pass


def _poll_text(path: str, *, timeout: int) -> Optional[str]:
    """Wait for the output file to appear and stop growing, then return its
    text. Returns None if it never appears within `timeout`."""
    deadline = time.time() + timeout
    last = -1
    while time.time() < deadline:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > 0 and size == last:        # non-empty and stable => done
                try:
                    with open(path) as fh:
                        return fh.read()
                except OSError:
                    pass
            last = size
        time.sleep(0.6)
    return None


def _drain(child: "pexpect.spawn") -> str:
    try:
        return child.read_nonblocking(size=1_000_000, timeout=2)
    except Exception:
        return ""
