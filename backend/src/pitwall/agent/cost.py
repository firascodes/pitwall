"""What one answer cost: token usage summed over every LLM call in a run, priced per 1M tokens."""

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.messages.ai import UsageMetadata, add_usage
from langchain_core.outputs import LLMResult


class CostMeter(BaseCallbackHandler):
    def __init__(self, input_usd_per_mtok: float, output_usd_per_mtok: float) -> None:
        self.prices = (input_usd_per_mtok, output_usd_per_mtok)
        self.calls = 0
        self.usage: UsageMetadata | None = None

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        message = getattr(response.generations[0][0], "message", None)
        if isinstance(message, AIMessage) and message.usage_metadata:
            self.calls += 1
            self.usage = add_usage(self.usage, message.usage_metadata)

    def report(self) -> dict[str, Any]:
        u: dict[str, Any] = dict(self.usage or {})
        tokens_in, tokens_out = u.get("input_tokens", 0), u.get("output_tokens", 0)
        usd = (tokens_in * self.prices[0] + tokens_out * self.prices[1]) / 1_000_000
        return {
            "llm_calls": self.calls,
            "input_tokens": tokens_in,
            "cached_tokens": u.get("input_token_details", {}).get("cache_read", 0),
            "output_tokens": tokens_out,
            "reasoning_tokens": u.get("output_token_details", {}).get("reasoning", 0),
            "usd": round(usd, 6),  # cached input is priced at the full rate: an upper bound
        }
