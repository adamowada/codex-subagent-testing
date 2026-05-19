# Stage 8: Usage Parsing

## Purpose

Stage 8 turns raw Codex JSONL event streams into stable token-accounting artifacts for each measured run. It is the bridge between execution evidence from Stage 6 and score/report computation in Stages 9 and 10.

The central goal is to measure not only whether a topology produced good code, but how much scarce GPT-5.5 usage it consumed to get there. Usage parsing must therefore preserve total token evidence even when model-level attribution is incomplete.

## Inputs

Each run directory should already contain these files before Stage 8 runs:

```text
events.jsonl
judge.events.jsonl
metadata.json
state.json
```

`events.jsonl` is the implementation Codex run event stream.

`judge.events.jsonl` is the blind judge Codex run event stream.

The run record from the expanded experiment matrix remains the source of truth for topology, root model, leaf model, Spark mode, and reasoning levels. Stage 8 should not infer topology from directory names.

## Outputs

Stage 8 writes:

```text
usage.json
```

The output should be valid JSON even when no usage events are found. Missing usage is a measurable artifact state, not a reason to drop the run.

Recommended schema:

```json
{
  "schema_version": 1,
  "implementation": {
    "input_tokens": 0,
    "cached_input_tokens": 0,
    "output_tokens": 0,
    "reasoning_output_tokens": 0,
    "total_tokens": 0
  },
  "judge": {
    "input_tokens": 0,
    "cached_input_tokens": 0,
    "output_tokens": 0,
    "reasoning_output_tokens": 0,
    "total_tokens": 0
  },
  "totals": {
    "implementation_tokens": 0,
    "judge_tokens": 0,
    "judge_inclusive_tokens": 0,
    "gpt55_implementation_tokens": null,
    "gpt55_judge_inclusive_tokens": null,
    "spark_implementation_tokens": null
  },
  "event_counts": {
    "implementation_usage_events": 0,
    "judge_usage_events": 0
  },
  "model_totals": {},
  "attribution_method": "unattributed_total",
  "warnings": []
}
```

## Parsing Contract

The expected Codex usage event is `turn.completed.usage`, but the parser should remain permissive because JSONL schemas can drift across Codex versions.

Accepted locations:

```text
event["usage"]
event["turn"]["usage"]
event["completed"]["usage"] when event["type"] == "turn.completed"
```

Accepted token aliases:

```text
input_tokens or prompt_tokens
cached_input_tokens or cached_tokens
output_tokens or completion_tokens
reasoning_output_tokens or reasoning_tokens
```

Nested detail objects should also be supported when present:

```text
input_tokens_details.cached_tokens
output_tokens_details.reasoning_tokens
```

Malformed JSONL lines, non-object events, and non-usage events should be ignored for token totals, while the raw files remain preserved as forensic evidence.

## Token Semantics

Stage 8 should track these fields separately:

```text
input_tokens
cached_input_tokens
output_tokens
reasoning_output_tokens
```

`total_tokens` should be computed as:

```text
input_tokens + output_tokens
```

Cached input and reasoning output are not added again to `total_tokens`, because providers commonly include them inside input and output token counts already. They are retained as separate dimensions for analysis and future cost modeling.

## Attribution Strategy

The benchmark cares most about implementation-only GPT-5.5 usage. That is the primary scarce-resource denominator for efficiency comparisons.

Attribution should follow this order:

1. If usage events expose a model name per event, aggregate exact per-model totals.
2. If the run has no Spark leaves and the root model is GPT-5.5, treat implementation total as GPT-5.5 implementation usage.
3. If the run is mixed-agent and lacks per-model attribution, preserve total implementation usage and mark GPT-5.5/Spark attribution as best effort.

Suggested attribution method labels:

```text
per_event_model
solo_total_as_gpt55
best_effort_total_as_gpt55_upper_bound
unattributed_total
```

For mixed-agent unattributed runs, `gpt55_implementation_tokens` may be recorded as an upper bound using total implementation tokens. This is conservative for efficiency scoring because it avoids making mixed Spark topologies look cheaper than the evidence supports.

Whenever attribution is incomplete, `warnings` should explain the limitation in plain language.

## Judge Usage

Judge runs are separate from implementation runs. Stage 8 should compute both:

```text
implementation_tokens
judge_tokens
judge_inclusive_tokens
```

The primary benchmark metric should use implementation-only GPT-5.5 tokens when available. Judge-inclusive GPT-5.5 usage should also be retained for sensitivity analysis, because judge calls can be expensive and may matter for end-to-end experiment cost.

## Resume Behavior

Stage 8 is restartable.

If `usage.json` exists and the `usage_parsed` phase is marked completed, resume should skip parsing unless rerun-failed or explicit rerun behavior requests regeneration.

If `usage.json` is missing, corrupt, or fails artifact validation, the phase should rerun.

Reruns should not mutate raw `events.jsonl` or `judge.events.jsonl`.

## Failure Handling

Usage parsing should be failure-tolerant:

- Missing implementation JSONL should produce zero implementation totals and a warning.
- Missing judge JSONL should produce zero judge totals and a warning.
- Malformed lines should be skipped without aborting the run.
- Unknown token fields should not break parsing.
- Missing model attribution should never cause total usage to be dropped.

Only infrastructure-level issues, such as inability to write `usage.json`, should fail the phase.

## Downstream Consumers

Stage 9 scoring reads `usage.json` to compute:

```text
quality_per_gpt55_impl_token
quality_per_judge_inclusive_gpt55_token
quality_per_total_impl_token
```

Stage 10 reporting reads the same artifact to populate per-run rows, aggregate token summaries, and limitations around attribution confidence.

Reports should surface attribution warnings rather than hiding them in raw JSON.

## Current Implementation Notes

The current implementation is centered in:

```text
harness/jsonl_usage.py
```

Key responsibilities:

- `parse_usage_events` reads JSONL and extracts normalized usage events.
- `normalize_usage` maps schema variants into stable token fields.
- `summarize_usage` combines implementation and judge streams.
- `write_usage_summary` writes the final `usage.json` artifact.

The orchestrator calls Stage 8 from `parse_usage_and_score` after judging and before scoring.

## Test Plan

Unit tests should cover:

- A standard `turn.completed` usage event.
- Top-level `usage` events.
- Nested `turn.usage` events.
- Nested `completed.usage` events.
- Token alias handling for prompt/completion naming.
- Cached token extraction from detail objects.
- Reasoning token extraction from detail objects.
- Missing files producing zero totals and warnings.
- Malformed JSONL lines being skipped.
- Per-event model attribution.
- Mixed Spark runs without per-model attribution producing best-effort warnings.
- Judge-inclusive totals.

Integration tests can use a fake Codex executable that writes synthetic JSONL for implementation and judge runs, allowing end-to-end verification without spending model tokens.

## Acceptance Checklist

- `usage.json` is written for every run.
- Implementation and judge token totals are present.
- Judge-inclusive totals are present.
- Implementation-only GPT-5.5 tokens are recorded when observable.
- Spark implementation tokens are recorded when observable.
- Model-level attribution method is explicit.
- Missing or ambiguous attribution is warned about without dropping total usage.
- Scoring consumes `usage.json` without needing raw JSONL.
- Report data includes usage and attribution fields.
- Resume can skip completed usage parsing and rerun invalid usage artifacts.

