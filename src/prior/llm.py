"""Thin wrapper over the model, with a pluggable backend.

Three backends, selected by `PRIOR_LLM_BACKEND`:

  "api"          (default) — the Anthropic API via the SDK. Forces a single tool
                 so structured output is guaranteed valid JSON. Costs metered
                 API credits (the hackathon's ANTHROPIC_API_KEY).

  "claude-code"  — routes through the Claude Agent SDK. NOTE: the SDK (like
                 `-p/--print`) now meters against API credits, so this no longer
                 saves credits — kept for compatibility. Asks for JSON-only and
                 parses it (with retries).

  "claude-cli"   — drives the *interactive* Claude Code TUI through a PTY (see
                 `claude_cli.py`). This is the only path that runs on the Claude
                 Code login (Max plan) WITHOUT metering API credits. The model
                 writes its JSON to a file we then read.

Everything downstream (Reader/Cartographer/Navigator) calls `structured()` /
`text()` and is backend-agnostic.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # only the "api" backend needs the SDK; keep import lazy
    import anthropic

_client: "Optional[anthropic.Anthropic]" = None


def client() -> "anthropic.Anthropic":
    global _client
    if _client is None:
        import anthropic  # lazy: the credit-free claude-cli backend doesn't need it
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
    timeout: int | None = None,
) -> dict[str, Any]:
    """Return a dict matching `schema` (a JSON-Schema object). Raises on
    persistent failure rather than returning malformed data. `timeout` (seconds)
    bounds a single claude-cli call; ignored by the other backends."""
    if backend() == "claude-cli":
        return _structured_claude_cli(
            model=model, system=system, user=user, schema=schema,
            retries=retries, timeout=timeout)
    if backend() == "claude-code":
        return _structured_claude_code(
            model=model, system=system, user=user, schema=schema, retries=retries)
    if backend() in ("openai", "vllm", "ollama"):
        return _structured_openai(
            model=model, system=system, user=user, schema=schema,
            max_tokens=max_tokens, retries=retries, timeout=timeout)
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
    import anthropic  # lazy; only the api backend needs the SDK
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


# ── Claude CLI (interactive PTY, no metered credits) backend ────────────────────
def _structured_claude_cli(*, model, system, user, schema, retries, timeout=None):
    from . import claude_cli  # lazy: only this backend needs pexpect
    kw = {"timeout": timeout} if timeout else {}
    if model:
        kw["model"] = model            # force e.g. opus for a second-model judge
    last_err: Optional[Exception] = None
    for _ in range(max(1, min(retries, 2))):  # cap retries — a hung call is costly
        try:
            return claude_cli.run_json(system=system, user=user, schema=schema, **kw)
        except Exception as e:  # noqa: BLE001 — surface after retries
            last_err = e
    raise RuntimeError(f"structured() (claude-cli) failed: {last_err}")


# ── OpenAI-compatible backend (vLLM / Ollama / any /v1) ─────────────────────────
def _structured_openai(*, model, system, user, schema, max_tokens, retries, timeout=None):
    """Talk to an OpenAI-compatible chat endpoint (a local open-weight model served by
    vLLM or Ollama). JSON is requested via response_format + schema-in-prompt and parsed
    leniently. Used to run a cheap, independent open-weight judge on a local GPU.
    Reads PRIOR_OPENAI_BASE_URL (default http://127.0.0.1:8000/v1) and PRIOR_OPENAI_API_KEY."""
    import urllib.request  # stdlib; no new dependency
    base = os.environ.get("PRIOR_OPENAI_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
    key = os.environ.get("PRIOR_OPENAI_API_KEY", "EMPTY")
    sys_json = (system + "\n\nReturn ONLY a single JSON object conforming to this JSON "
                "Schema. No prose, no markdown fences:\n" + json.dumps(schema))
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": sys_json},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }).encode()
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                base + "/chat/completions", data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=timeout or 120) as r:
                payload = json.loads(r.read())
            return extract_json(payload["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001 — surface after retries
            last_err = e
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"structured() (openai) failed after {retries} attempts: {last_err}")


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
            allowed_tools=[],   # pure generation; no file/bash/web tools
            max_turns=1,
            model=model,
        )
        chunks: list[str] = []
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
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
