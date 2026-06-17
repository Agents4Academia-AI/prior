"""Thin wrapper over the Anthropic SDK.

One job: get *structured* output back reliably. We do that by giving the model a
single tool whose input_schema is the shape we want, and forcing that tool — so
the model must return JSON matching the schema instead of prose.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import anthropic

_client: Optional[anthropic.Anthropic] = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


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
    """Return a dict matching `schema` (a JSON-Schema object).

    Raises on persistent failure rather than returning malformed data — callers
    decide how to degrade.
    """
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


def text(*, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """A plain prose completion (used by Navigator for the final answer)."""
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")
