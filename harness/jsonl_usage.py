from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


GPT55_MODEL = "gpt-5.5"
SPARK_MODEL = "gpt-5.3-codex-spark"
TOKEN_KEYS = {
    "input_tokens": ("input_tokens", "prompt_tokens"),
    "cached_input_tokens": ("cached_input_tokens", "cached_tokens"),
    "output_tokens": ("output_tokens", "completion_tokens"),
    "reasoning_output_tokens": ("reasoning_output_tokens", "reasoning_tokens"),
}
USAGE_TOTAL_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


@dataclass(frozen=True)
class UsageParseResult:
    events: list[dict[str, Any]]
    warnings: list[str]
    malformed_lines: int = 0
    non_object_lines: int = 0


def parse_usage_events(path: str | Path) -> list[dict[str, Any]]:
    """Parse usage records from Codex JSONL events."""

    return parse_usage_file(path, label="usage").events


def parse_usage_file(path: str | Path, *, label: str) -> UsageParseResult:
    """Parse usage records and warnings from one Codex JSONL stream."""

    events_path = Path(path)
    warnings: list[str] = []
    if not events_path.exists():
        return UsageParseResult([], [f"{label} JSONL file is missing: {events_path}"])

    usage_events: list[dict[str, Any]] = []
    malformed_lines = 0
    non_object_lines = 0
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if not isinstance(event, Mapping):
            non_object_lines += 1
            continue

        usage = _find_turn_usage(event)
        if usage is None:
            continue

        normalized = normalize_usage(usage)
        normalized["line_number"] = line_number
        model = _find_model(event, usage)
        if isinstance(model, str):
            normalized["model"] = model
        usage_events.append(normalized)

    if malformed_lines:
        warnings.append(f"{label} JSONL skipped {malformed_lines} malformed line(s).")
    if non_object_lines:
        warnings.append(f"{label} JSONL skipped {non_object_lines} non-object line(s).")
    if not usage_events:
        warnings.append(f"{label} JSONL contained no usage events: {events_path}")

    return UsageParseResult(usage_events, warnings, malformed_lines, non_object_lines)


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
    implementation_parse = parse_usage_file(implementation_events_path, label="Implementation")
    judge_parse = parse_usage_file(judge_events_path, label="Judge")
    implementation_events = implementation_parse.events
    judge_events = judge_parse.events

    implementation = _sum_usage(implementation_events)
    judge = _sum_usage(judge_events)
    model_totals = _model_totals(implementation_events + judge_events)
    implementation_model_totals = _model_totals(implementation_events)
    judge_model_totals = _model_totals(judge_events)
    root_model = str(run.get("root", {}).get("model", "unknown")) if isinstance(run.get("root"), Mapping) else "unknown"
    judge_model = (
        str(run.get("judge", {}).get("model", "unknown")) if isinstance(run.get("judge"), Mapping) else "unknown"
    )
    has_spark = bool(run.get("leaf"))

    warnings = [*implementation_parse.warnings, *judge_parse.warnings]
    attribution = _implementation_attribution(
        implementation_events,
        implementation,
        root_model=root_model,
        has_spark=has_spark,
    )
    warnings.extend(attribution["warnings"])

    judge_gpt55_tokens = _judge_gpt55_tokens(
        judge_events,
        judge,
        judge_model=judge_model,
    )
    gpt55_judge_inclusive_tokens = _nullable_sum(attribution["gpt55_implementation_tokens"], judge_gpt55_tokens)

    return {
        "schema_version": 1,
        "implementation": implementation,
        "judge": judge,
        "totals": {
            "implementation_tokens": implementation["total_tokens"],
            "judge_tokens": judge["total_tokens"],
            "judge_inclusive_tokens": implementation["total_tokens"] + judge["total_tokens"],
            "gpt55_implementation_tokens": attribution["gpt55_implementation_tokens"],
            "gpt55_judge_tokens": judge_gpt55_tokens,
            "gpt55_judge_inclusive_tokens": gpt55_judge_inclusive_tokens,
            "spark_implementation_tokens": attribution["spark_implementation_tokens"],
        },
        "event_counts": {
            "implementation_usage_events": len(implementation_events),
            "judge_usage_events": len(judge_events),
        },
        "model_totals": model_totals,
        "implementation_model_totals": implementation_model_totals,
        "judge_model_totals": judge_model_totals,
        "unattributed": {
            "implementation_tokens": _unattributed_tokens(implementation_events),
            "judge_tokens": _unattributed_tokens(judge_events),
        },
        "attribution_method": attribution["attribution_method"],
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
        turn_completed = turn.get("completed")
        if isinstance(turn_completed, Mapping) and isinstance(turn_completed.get("usage"), Mapping):
            return turn_completed["usage"]

    if event.get("type") == "turn.completed":
        completed = event.get("completed")
        if isinstance(completed, Mapping) and isinstance(completed.get("usage"), Mapping):
            return completed["usage"]

    return None


def _find_model(event: Mapping[str, Any], usage: Mapping[str, Any]) -> str | None:
    for candidate in (
        event.get("model"),
        usage.get("model"),
        _nested_value(event, ("turn", "model")),
        _nested_value(event, ("completed", "model")),
        _nested_value(event, ("turn", "completed", "model")),
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _nested_value(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _number_from(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            number = int(value)
            if number >= 0:
                return number
    return 0


def _sum_usage(events: list[dict[str, Any]]) -> dict[str, int]:
    total = {key: 0 for key in USAGE_TOTAL_KEYS}
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
            {key: 0 for key in USAGE_TOTAL_KEYS},
        )
        for key in bucket:
            bucket[key] += int(event.get(key, 0))
    return totals


def _implementation_attribution(
    events: list[dict[str, Any]],
    total: Mapping[str, int],
    *,
    root_model: str,
    has_spark: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    total_tokens = int(total.get("total_tokens", 0))
    unattributed_tokens = _unattributed_tokens(events)
    model_totals = _model_totals(events)

    if total_tokens == 0:
        return {
            "attribution_method": "unattributed_total",
            "gpt55_implementation_tokens": 0,
            "spark_implementation_tokens": 0 if model_totals else None,
            "warnings": warnings,
        }

    if model_totals and unattributed_tokens == 0:
        return {
            "attribution_method": "per_event_model",
            "gpt55_implementation_tokens": _tokens_for_model(model_totals, GPT55_MODEL),
            "spark_implementation_tokens": _tokens_for_model(model_totals, SPARK_MODEL),
            "warnings": warnings,
        }

    if model_totals and unattributed_tokens > 0:
        warnings.append(
            "Implementation JSONL exposed model attribution for some usage events only; "
            "GPT-5.5/Spark split is best effort."
        )
        return {
            "attribution_method": "partial_per_event_model_with_gpt55_upper_bound",
            "gpt55_implementation_tokens": total_tokens,
            "spark_implementation_tokens": _tokens_for_model(model_totals, SPARK_MODEL),
            "warnings": warnings,
        }

    if not has_spark and root_model == GPT55_MODEL:
        return {
            "attribution_method": "solo_total_as_gpt55",
            "gpt55_implementation_tokens": total_tokens,
            "spark_implementation_tokens": None,
            "warnings": warnings,
        }

    if has_spark:
        warnings.append(
            "Implementation JSONL did not expose per-model attribution; "
            "GPT-5.5/Spark split is best effort."
        )
        return {
            "attribution_method": "best_effort_total_as_gpt55_upper_bound",
            "gpt55_implementation_tokens": total_tokens,
            "spark_implementation_tokens": None,
            "warnings": warnings,
        }

    warnings.append("Implementation JSONL did not expose model attribution.")
    return {
        "attribution_method": "unattributed_total",
        "gpt55_implementation_tokens": None,
        "spark_implementation_tokens": None,
        "warnings": warnings,
    }


def _judge_gpt55_tokens(events: list[dict[str, Any]], total: Mapping[str, int], *, judge_model: str) -> int | None:
    total_tokens = int(total.get("total_tokens", 0))
    if total_tokens == 0:
        return 0

    model_totals = _model_totals(events)
    unattributed_tokens = _unattributed_tokens(events)
    if model_totals and unattributed_tokens == 0:
        return _tokens_for_model(model_totals, GPT55_MODEL)
    if judge_model == GPT55_MODEL:
        return total_tokens
    return None


def _unattributed_tokens(events: list[dict[str, Any]]) -> int:
    return sum(int(event.get("total_tokens", 0)) for event in events if not isinstance(event.get("model"), str))


def _tokens_for_model(model_totals: Mapping[str, Any], model: str) -> int:
    bucket = model_totals.get(model)
    if not isinstance(bucket, Mapping):
        return 0
    return int(bucket.get("total_tokens", 0))


def _nullable_sum(*values: int | None) -> int | None:
    total = 0
    for value in values:
        if value is None:
            return None
        total += value
    return total
