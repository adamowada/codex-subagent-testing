from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


TOKEN_KEYS = {
    "input_tokens": ("input_tokens", "prompt_tokens"),
    "cached_input_tokens": ("cached_input_tokens", "cached_tokens"),
    "output_tokens": ("output_tokens", "completion_tokens"),
    "reasoning_output_tokens": ("reasoning_output_tokens", "reasoning_tokens"),
}


def parse_usage_events(path: str | Path) -> list[dict[str, Any]]:
    """Parse usage records from Codex JSONL events."""

    events_path = Path(path)
    if not events_path.exists():
        return []

    usage_events: list[dict[str, Any]] = []
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, Mapping):
            continue

        usage = _find_turn_usage(event)
        if usage is None:
            continue

        normalized = normalize_usage(usage)
        normalized["line_number"] = line_number
        model = event.get("model") or usage.get("model")
        if isinstance(model, str):
            normalized["model"] = model
        usage_events.append(normalized)

    return usage_events


def normalize_usage(usage: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {
        "input_tokens": _number_from(usage, TOKEN_KEYS["input_tokens"]),
        "cached_input_tokens": _number_from(usage, TOKEN_KEYS["cached_input_tokens"]),
        "output_tokens": _number_from(usage, TOKEN_KEYS["output_tokens"]),
        "reasoning_output_tokens": _number_from(usage, TOKEN_KEYS["reasoning_output_tokens"]),
    }

    input_details = usage.get("input_tokens_details")
    if isinstance(input_details, Mapping) and normalized["cached_input_tokens"] == 0:
        normalized["cached_input_tokens"] = _number_from(input_details, ("cached_tokens", "cached_input_tokens"))

    output_details = usage.get("output_tokens_details")
    if isinstance(output_details, Mapping) and normalized["reasoning_output_tokens"] == 0:
        normalized["reasoning_output_tokens"] = _number_from(
            output_details,
            ("reasoning_tokens", "reasoning_output_tokens"),
        )

    # Cached input and reasoning output are tracked separately because providers
    # often include them inside input_tokens/output_tokens already.
    normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]
    return normalized


def summarize_usage(
    *,
    implementation_events_path: str | Path,
    judge_events_path: str | Path,
    run: Mapping[str, Any],
) -> dict[str, Any]:
    implementation_events = parse_usage_events(implementation_events_path)
    judge_events = parse_usage_events(judge_events_path)

    implementation = _sum_usage(implementation_events)
    judge = _sum_usage(judge_events)
    model_totals = _model_totals(implementation_events + judge_events)
    root_model = str(run.get("root", {}).get("model", "unknown")) if isinstance(run.get("root"), Mapping) else "unknown"
    has_spark = bool(run.get("leaf"))

    attribution_method = "per_event_model" if model_totals else "unattributed_total"
    warnings: list[str] = []
    gpt55_impl_tokens: int | None = None
    spark_impl_tokens: int | None = None

    if model_totals:
        gpt55_impl_tokens = sum(
            event["total_tokens"]
            for event in implementation_events
            if event.get("model") == "gpt-5.5"
        )
        spark_impl_tokens = sum(
            event["total_tokens"]
            for event in implementation_events
            if event.get("model") == "gpt-5.3-codex-spark"
        )
    else:
        gpt55_impl_tokens = implementation["total_tokens"]
        attribution_method = (
            "solo_total_as_gpt55" if not has_spark and root_model == "gpt-5.5"
            else "best_effort_total_as_gpt55_upper_bound"
        )
        if has_spark:
            warnings.append("Implementation JSONL did not expose per-model attribution; GPT-5.5/Spark split is best effort.")

    return {
        "schema_version": 1,
        "implementation": implementation,
        "judge": judge,
        "totals": {
            "implementation_tokens": implementation["total_tokens"],
            "judge_tokens": judge["total_tokens"],
            "judge_inclusive_tokens": implementation["total_tokens"] + judge["total_tokens"],
            "gpt55_implementation_tokens": gpt55_impl_tokens,
            "gpt55_judge_inclusive_tokens": (gpt55_impl_tokens or 0) + judge["total_tokens"],
            "spark_implementation_tokens": spark_impl_tokens,
        },
        "event_counts": {
            "implementation_usage_events": len(implementation_events),
            "judge_usage_events": len(judge_events),
        },
        "model_totals": model_totals,
        "attribution_method": attribution_method,
        "warnings": warnings,
    }


def write_usage_summary(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_turn_usage(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    usage = event.get("usage")
    if isinstance(usage, Mapping):
        return usage

    turn = event.get("turn")
    if isinstance(turn, Mapping):
        turn_usage = turn.get("usage")
        if isinstance(turn_usage, Mapping):
            return turn_usage

    if event.get("type") == "turn.completed":
        completed = event.get("completed")
        if isinstance(completed, Mapping) and isinstance(completed.get("usage"), Mapping):
            return completed["usage"]

    return None


def _number_from(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _sum_usage(events: list[dict[str, Any]]) -> dict[str, int]:
    total = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
    for event in events:
        for key in total:
            total[key] += int(event.get(key, 0))
    return total


def _model_totals(events: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    for event in events:
        model = event.get("model")
        if not isinstance(model, str):
            continue
        bucket = totals.setdefault(
            model,
            {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "total_tokens": 0,
            },
        )
        for key in bucket:
            bucket[key] += int(event.get(key, 0))
    return totals
