"""Thin wrapper over the model, with a pluggable backend.

Two backends, selected by `PRIOR_LLM_BACKEND`:

  "api"          (default) — the Anthropic API via the SDK. Forces a single tool
                 so structured output is guaranteed valid JSON. Costs metered
                 API credits (the hackathon's ANTHROPIC_API_KEY).

  "claude-code"  — routes through the Claude Agent SDK, which runs on your
                 Claude Code login (e.g. a Max subscription) when no API key is
                 set. Lets the whole Prior pipeline run on a flat-rate plan
                 instead of burning API credits. The Agent SDK has no forced-tool
                 knob, so we ask for JSON-only and parse it (with retries).

Everything downstream (Reader/Cartographer/Navigator) calls `structured()` /
`text()` and is backend-agnostic.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any, Optional

import anthropic

_client: Optional[anthropic.Anthropic] = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


def backend() -> str:
    return os.environ.get("PRIOR_LLM_BACKEND", "api").lower()


# ── public API ────────────────────────────────────────────────────────────────
def structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    tool_name: str = "emit",
    max_tokens: int = 4096,
    retries: int = 3,
) -> dict[str, Any]:
    """Return a dict matching `schema` (a JSON-Schema object). Raises on
    persistent failure rather than returning malformed data."""
    if backend() == "claude-code":
        return _structured_claude_code(
            model=model, system=system, user=user, schema=schema, retries=retries)
    return _structured_api(
        model=model, system=system, user=user, schema=schema,
        tool_name=tool_name, max_tokens=max_tokens, retries=retries)


def text(*, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """A plain prose completion (used by Navigator for the final answer)."""
    if backend() == "claude-code":
        return _run_claude_code(system=system, prompt=user, model=model)
    resp = client().messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


# ── API backend ──────────────────────────────────────────────────────────────
def _structured_api(*, model, system, user, schema, tool_name, max_tokens, retries):
    tool = {
        "name": tool_name,
        "description": "Return the result in exactly this structure.",
        "input_schema": schema,
    }
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = client().messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return block.input  # type: ignore[return-value]
            raise ValueError("model did not call the emit tool")
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            last_err = e
            time.sleep(2 ** attempt)
        except Exception as e:  # noqa: BLE001 — surface after retries
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"structured() failed after {retries} attempts: {last_err}")


# ── Claude Code (Agent SDK) backend ────────────────────────────────────────────
def _structured_claude_code(*, model, system, user, schema, retries):
    sys_json = (
        system
        + "\n\nRespond with ONLY a single JSON object that conforms to this "
        "JSON Schema. No prose, no markdown fences, no commentary:\n"
        + json.dumps(schema)
    )
    last_err: Optional[Exception] = None
    for _ in range(retries):
        raw = _run_claude_code(system=sys_json, prompt=user, model=model)
        try:
            return extract_json(raw)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"structured() (claude-code) failed: {last_err}")


def _run_claude_code(*, system: str, prompt: str, model: str) -> str:
    """Run one turn through the Agent SDK and return the concatenated text."""
    try:
        from claude_agent_sdk import (  # imported lazily; only this backend needs it
            query, ClaudeAgentOptions, AssistantMessage, TextBlock,
        )
    except ImportError as e:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "PRIOR_LLM_BACKEND=claude-code needs the Agent SDK: "
            "`pip install claude-agent-sdk` and be logged in to Claude Code."
        ) from e

    async def _go() -> str:
        opts = ClaudeAgentOptions(
            system_prompt=system,
            allowed_tools=[],     # pure generation; no file/bash/web tools
            setting_sources=[],   # don't load project skills/settings (bare model)
            max_turns=6,          # ceiling, not a target; open prompts may want >1 turn
            model=model,
        )
        chunks: list[str] = []
        try:
            async for msg in query(prompt=prompt, options=opts):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            chunks.append(block.text)
        except Exception:
            # The Agent SDK raises on e.g. "max turns reached" even after the
            # model has already produced its answer — salvage that text.
            if not chunks:
                raise
        return "".join(chunks)

    return asyncio.run(_go())


# ── helpers ──────────────────────────────────────────────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json(raw: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object out of a model's text response."""
    s = (raw or "").strip()
    m = _FENCE.search(s)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if 0 <= start < end:
            return json.loads(s[start:end + 1])
        raise
