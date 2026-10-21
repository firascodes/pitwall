from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from pitwall.agent.cost import CostMeter


def result(tokens_in: int, tokens_out: int, reasoning: int = 0) -> LLMResult:
    usage = {
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "output_token_details": {"reasoning": reasoning},
    }
    return LLMResult(generations=[[ChatGeneration(message=AIMessage("", usage_metadata=usage))]])


def test_meter_sums_calls_and_prices_per_million_tokens() -> None:
    meter = CostMeter(input_usd_per_mtok=0.10, output_usd_per_mtok=0.50)
    meter.on_llm_end(result(1_000_000, 0))
    meter.on_llm_end(result(0, 1_000_000, reasoning=400))
    report = meter.report()
    assert report["llm_calls"] == 2
    assert report["input_tokens"] == report["output_tokens"] == 1_000_000
    assert report["reasoning_tokens"] == 400
    assert report["usd"] == 0.6


def test_meter_with_no_calls_costs_nothing() -> None:
    assert CostMeter(0.1, 0.5).report() == {
        "llm_calls": 0,
        "input_tokens": 0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "usd": 0.0,
    }
