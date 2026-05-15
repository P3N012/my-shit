"""
Anthropic SDK wrapper.

One place that talks to the Anthropic API. Higher layers
(`app/services/ai_service.py`, the arq worker) call this wrapper and
never touch the SDK directly, so model defaults, prompt caching, and
the usage-recording contract stay in one place.

Defaults applied here (overridable per call):
- model: settings.ANTHROPIC_MODEL (claude-opus-4-7)
- adaptive thinking: enabled
- top-level cache_control={"type": "ephemeral"} on every call so the
  last cacheable block is auto-cached. The skill calls this out as the
  simplest reliable form of caching; the prefix the API auto-picks is
  almost always the system prompt + early stable messages.

This module is intentionally synchronous. The Anthropic SDK exposes
both sync and async clients; the FastAPI handlers run blocking SDK
calls in the threadpool. We can switch to AsyncAnthropic later if we
need streaming or genuine concurrency inside a single worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import anthropic

from app.core.config import settings


# Per-million-token prices in USD. Update when Anthropic publishes new
# pricing. Cache writes are ~1.25x input; cache reads are ~0.1x input.
MODEL_PRICING: Dict[str, Dict[str, Decimal]] = {
    "claude-opus-4-7": {
        "input": Decimal("5.00"),
        "output": Decimal("25.00"),
    },
    "claude-opus-4-6": {
        "input": Decimal("5.00"),
        "output": Decimal("25.00"),
    },
    "claude-sonnet-4-6": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "claude-haiku-4-5": {
        "input": Decimal("1.00"),
        "output": Decimal("5.00"),
    },
}
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
CACHE_READ_MULTIPLIER = Decimal("0.10")


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_response(cls, usage_obj: Any) -> "TokenUsage":
        return cls(
            input_tokens=getattr(usage_obj, "input_tokens", 0) or 0,
            output_tokens=getattr(usage_obj, "output_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage_obj, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(usage_obj, "cache_read_input_tokens", 0) or 0,
        )


@dataclass
class CompletionResult:
    """Outcome of one `messages.create()` call — what the higher layer needs to record."""
    text: str
    model: str
    stop_reason: Optional[str]
    usage: TokenUsage
    cost_usd: Decimal
    raw: Any  # the full SDK Message, in case callers want content blocks


def estimate_cost(model: str, usage: TokenUsage) -> Decimal:
    """USD cost for a single completion based on MODEL_PRICING.

    Models not in the pricing table return Decimal("0") rather than
    raising, so an experimental model never breaks usage recording.
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return Decimal("0")
    in_per_token = pricing["input"] / Decimal(1_000_000)
    out_per_token = pricing["output"] / Decimal(1_000_000)
    cost = (
        Decimal(usage.input_tokens) * in_per_token
        + Decimal(usage.cache_creation_input_tokens) * in_per_token * CACHE_WRITE_MULTIPLIER
        + Decimal(usage.cache_read_input_tokens) * in_per_token * CACHE_READ_MULTIPLIER
        + Decimal(usage.output_tokens) * out_per_token
    )
    return cost.quantize(Decimal("0.000001"))


_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    """Lazy singleton; defers SDK instantiation until first call.

    This lets tests run without ANTHROPIC_API_KEY set as long as they
    don't actually hit the SDK.
    """
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it in the environment to enable AI features."
            )
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def create_message(
    messages: List[Dict[str, Any]],
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: bool = True,
) -> CompletionResult:
    """
    Make one synchronous Anthropic Messages call.

    `messages` is the standard role/content list. `system` is optional;
    when present it's passed as a string (sufficient for auto-caching).
    `max_tokens` defaults to settings.ANTHROPIC_MAX_TOKENS — the caller
    should bump it for long outputs and switch to streaming.
    """
    client = get_client()
    selected_model = model or settings.ANTHROPIC_MODEL
    selected_max_tokens = max_tokens or settings.ANTHROPIC_MAX_TOKENS

    kwargs: Dict[str, Any] = {
        "model": selected_model,
        "max_tokens": selected_max_tokens,
        "messages": messages,
        # Top-level auto-caching: the SDK marks the last cacheable block
        # with cache_control. For a stable system prompt + frozen prefix
        # this gets us cache hits without manual breakpoint placement.
        "cache_control": {"type": "ephemeral"},
    }
    if system:
        kwargs["system"] = system
    if enable_thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    response = client.messages.create(**kwargs)

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    text = "".join(text_blocks)

    usage = TokenUsage.from_response(response.usage)
    cost = estimate_cost(selected_model, usage)

    return CompletionResult(
        text=text,
        model=selected_model,
        stop_reason=getattr(response, "stop_reason", None),
        usage=usage,
        cost_usd=cost,
        raw=response,
    )
