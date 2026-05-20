# Stage 17: Build The V2 Oracle And Hidden Case Generator

## Purpose

Stage 17 turns the RuleLedger v2 semantic contract into private, deterministic
benchmark assets. Stage 16 made the hard-mode behavior explicit and visible to
measured agents. Stage 17 should build the independent oracle and generated
hidden cases that later stages can execute and score.

This stage should answer:

```text
Can the benchmark generate a frozen v2 hidden suite from one private oracle,
with stable hashes, documented categories, and no hidden-data leakage into
starter projects, prompts, or run worktrees?
```

Stage 17 is an asset-generation stage. It should avoid broad hidden-runner
execution changes, final scoring calibration, or report changes except where
small tests are needed to prove the generated assets are valid.

## Scope

Stage 17 owns:

- Implementing a private RuleLedger v2 oracle independent from
  `benchmark_template_v2`.
- Encoding Stage 16 rule IDs and output contracts in oracle-generated expected
  values.
- Generating deterministic v2 hidden cases from a fixed seed.
- Replacing or superseding the placeholder v2 hidden cases directory with real
  generated v2 cases.
- Writing a manifest with case counts, category weights, points, seed, and
  per-file SHA-256 hashes.
- Covering the required v2 categories:
  - `parse_validation`
  - `normalization`
  - `bitemporal_replay`
  - `lifecycle_precedence`
  - `billing_proration`
  - `account_merges`
  - `metamorphic_invariants`
  - `performance`
  - `reporting`
  - `parity`
- Adding generator tests for determinism, manifest correctness, rule coverage,
  and privacy boundaries.

Stage 17 does not own:

- Upgrading `harness.hidden_runner` to execute every new v2 operation type.
- Changing v1 hidden cases or v1 hidden-runner behavior.
- Changing top-level scoring weights or report aggregation.
- Recalibrating experiment cells.
- Editing locked source-of-truth documents unless explicitly requested.
- Committing generated run output under `runs/`.

## Inputs

Stage 17 starts from:

```text
benchmark_template_v2/docs/ruleledger_v2_semantics.md
hidden_tests/generators/ruleledger_v2_semantics.py
hidden_tests/cases_v2_placeholder/
configs/ruleledger_v2.yaml
configs/scoring_v2.yaml
harness/hidden_runner.py
plans/stage-16-specify-hard-mode-semantics.md
```

The Stage 16 semantics document is the public rule contract. The private v2
oracle should treat that document, plus `ruleledger_v2_semantics.py`, as the
source of rule identifiers, summary fields, and CSV header order.

## Recommended Outputs

Add the oracle and generator under `hidden_tests/generators/`:

```text
hidden_tests/generators/ruleledger_v2_oracle.py
hidden_tests/generators/generate_v2_cases.py
```

Generate real v2 hidden cases into a separate directory:

```text
hidden_tests/cases_v2/
  manifest.json
  parse_validation.json
  normalization.json
  bitemporal_replay.json
  lifecycle_precedence.json
  billing_proration.json
  account_merges.json
  metamorphic_invariants.json
  performance.json
  reporting.json
  parity.json
```

Update the v2 experiment config to point at the real v2 hidden suite:

```text
configs/ruleledger_v2.yaml
```

Add focused tests, likely in a new file:

```text
tests/test_stage17_v2_oracle_generator.py
```

## Oracle Design

The v2 oracle should be private benchmark infrastructure. It must not import
from `benchmark_template_v2`, because the starter implementation is
intentionally incomplete and visible to measured agents.

Recommended oracle responsibilities:

- Parse event lines and normalize raw events.
- Validate required fields and known optional fields.
- Normalize timestamps, money, currency, sequence, quantity, seat deltas,
  account merge fields, correction fields, void fields, invoice fields, and
  billing periods.
- Build business-state views from separate business and audit cutoffs.
- Apply replay ordering by `(effectiveAt, recordedAt, sequence, id)`.
- Apply duplicate event id handling after normalization.
- Apply corrections and voids according to recorded-time visibility.
- Reduce lifecycle state for all v2 statuses.
- Apply account merges and canonical account reporting.
- Calculate billing and prorations using integer or rational arithmetic.
- Export stable summaries using `V2_SUMMARY_FIELDS`.
- Export stable CSV using `V2_CSV_HEADER`.
- Produce exact expected outputs for all generated hidden operation types.

Keep the oracle straightforward and heavily factored around the semantic
domains. Correctness and readability matter more than brevity.

## Case Schema

Keep the existing hidden-case privacy shape:

```json
{
  "id": "bitemporal.late_arrival.visible_after_recorded_at",
  "category": "bitemporal_replay",
  "rule_ids": ["BT-004", "BT-005", "OR-001"],
  "operation": "v2_reduce_and_summarize",
  "languages": ["typescript", "python"],
  "points": 2.0,
  "input": {},
  "expected": {}
}
```

The generator may use richer operation names than the current hidden runner
supports. Stage 18 will add execution support. Stage 17 should still validate
that the oracle can produce each expected value.

Recommended operation families:

- `parse_line`
- `normalize_event`
- `v2_reduce_and_summarize`
- `v2_reduce_and_evaluate`
- `v2_export_report`
- `v2_metamorphic`
- `v2_performance`
- `v2_parity`

Each generated case should include:

- Stable `id`.
- Public category name.
- One or more `rule_ids`.
- Operation name.
- Language target list.
- Numeric points.
- Hidden input payload.
- Oracle-produced expected output.

## Manifest Schema

The manifest should stay public enough for validation and reporting without
revealing hidden inputs or expected outputs outside `hidden_tests/`.

Recommended manifest shape:

```json
{
  "schema_version": 2,
  "benchmark": "ruleledger_v2",
  "seed": 20260520,
  "generated_at": "2026-05-20T00:00:00.000Z",
  "category_weights": {
    "parse_validation": 0.08,
    "normalization": 0.10,
    "bitemporal_replay": 0.14,
    "lifecycle_precedence": 0.13,
    "billing_proration": 0.13,
    "account_merges": 0.11,
    "metamorphic_invariants": 0.13,
    "performance": 0.08,
    "reporting": 0.05,
    "parity": 0.05
  },
  "files": {
    "bitemporal_replay.json": {
      "case_count": 12,
      "points": 24.0,
      "sha256": "<hash>"
    }
  }
}
```

The exact weights can be tuned during implementation, but they should sum to a
meaningful distribution where hard-mode correctness dominates and no single
category overwhelms the suite.

## Category Plan

### Parse Validation

Cover invalid JSON, non-object JSON, blank lines, missing required fields,
blank required fields, invalid event types, invalid timestamps, invalid known
optional fields, invalid period boundaries, invalid currency codes, invalid
amounts, invalid quantities, and invalid sequence values.

Expected behavior should assert stable error codes and issue sets without
requiring implementations to expose raw hidden payloads in diagnostics.

### Normalization

Cover timestamp canonicalization, default `effectiveAt`, default `recordedAt`,
sequence defaults, money parsing, `amount_cents`, currency uppercasing, invoice
fields, billing periods, quantity, seat deltas, correction references, void
references, merge source ids, coupon codes, and ignored unknown fields.

Include cases where normalized field order matters only through JSON-compatible
value equality, not object insertion order.

### Bitemporal Replay

Cover late-arriving events, future-effective events, separate business/audit
cutoffs, single `asOf` compatibility, correction visibility by `recordedAt`,
void visibility by `recordedAt`, replay sort ties, and duplicate event id
handling.

These cases should prove that business time and audit time are not collapsed
accidentally.

### Lifecycle Precedence

Cover account open, trial start/end, plan changes, pause/resume,
cancel/reactivate, terminal close, payment failure/recovery, coupons, usage,
seat changes, and event ordering around status transitions.

Include cases where plan changes while paused or cancelled update stored plan
without restoring active entitlements.

### Billing Proration

Cover period validation, half-open periods, UTC millisecond proration,
half-away-from-zero rounding, seat and quantity multipliers, mid-period plan
changes, credits, charges, zero-length rejection, and negative adjustment
handling where allowed.

Use integer or rational arithmetic in the oracle. Avoid floating point for
expected money values.

### Account Merges

Cover destination canonicalization, source migration, duplicate ids across
lineages, post-merge source events, merge lineage ordering, source account
suppression from normal reports, and merged account CSV serialization.

Include at least one multi-hop merge so lineage and canonical ids are tested.

### Metamorphic Invariants

Add cases for:

- Shuffled equivalent input.
- Unrelated account injection.
- Duplicate idempotent events.
- Split usage batches.
- Replay stability across repeated reductions.
- Normalization stability.
- Cross-language exactness where applicable.

The expected output should describe the invariant result, not just one raw
summary.

### Performance

Generate moderate deterministic datasets in the 10k-50k event range. These
should catch obviously quadratic implementations without making runtime the
whole benchmark.

Performance cases should include:

- Many accounts with small histories.
- One account with a long history.
- Merge-heavy histories.
- Correction/void-heavy histories.
- Reporting over many summaries.

Stage 17 should generate and validate the cases. Stage 18 should decide final
timeout enforcement and result reporting.

### Reporting

Cover stable header order, row ordering, lowercase booleans, null-to-empty
serialization, array serialization with `|`, RFC 4180 escaping, invoice fields,
merged lineage fields, and byte-identical trailing newline behavior.

Include at least one case with commas, quotes, carriage returns, or newlines in
serializable fields if the public contract allows those values.

### Parity

Create shared fixtures where TypeScript and Python must produce equivalent
summaries and byte-identical CSV. These cases should be broad but not
redundant with every category-specific case.

Parity cases should emphasize cross-language pitfalls: timestamp formatting,
sort stability, money rounding, boolean serialization, list serialization, and
CSV escaping.

## Determinism Rules

Generation must be deterministic:

- Use one fixed v2 seed.
- Avoid wall-clock timestamps in generated case payloads.
- Use a fixed `generated_at` value in generated files.
- Sort JSON object keys when writing generated files.
- Write files with stable indentation and trailing newlines.
- Do not depend on platform-specific path ordering.
- Do not include absolute local paths in generated files.

Running the generator twice in a clean checkout should produce byte-identical
case files and manifest hashes.

## Privacy Rules

The generated hidden cases are private benchmark data:

- Do not copy generated v2 case files into `benchmark_template_v2/`.
- Do not paste hidden inputs or expected outputs into prompts.
- Do not include concrete hidden payloads in plans, reports, or run artifacts.
- Keep public documentation limited to rule names, category names, weights, and
  high-level behavior.
- Preserve opaque hidden-run result identifiers.
- Continue stripping metadata such as `rule_ids` before sending cases into
  measured language runners.

The hidden case manifest may expose category names, category weights, points,
case counts, and hashes. It should not expose concrete expected outputs outside
the case files themselves.

## Implementation Steps

1. Add `ruleledger_v2_oracle.py` with normalization helpers and summary/report
   constants wired to `ruleledger_v2_semantics.py`.
2. Implement timestamp, money, currency, sequence, quantity, seat, period, and
   reference normalization.
3. Implement v2 replay and state reduction around business/audit cutoffs.
4. Implement correction and void activation rules.
5. Implement lifecycle, billing, account merge, reporting, and parity helpers.
6. Add `generate_v2_cases.py` with deterministic writers and category builders.
7. Generate `hidden_tests/cases_v2/` from the fixed seed.
8. Update `configs/ruleledger_v2.yaml` to use `hidden_tests/cases_v2`.
9. Add tests for oracle behavior on small visible synthetic examples.
10. Add tests for generator determinism and manifest hashes.
11. Add tests that every v2 hidden case references documented rule IDs.
12. Add tests that every required category exists and has nonzero points.
13. Add privacy tests or extend existing validation tests for the selected v2
    hidden case directory.
14. Run the focused stage tests and the full repo test suite.

## Verification

Recommended commands:

```powershell
python hidden_tests/generators/generate_v2_cases.py
python -m pytest tests/test_stage16_semantics.py tests/test_stage17_v2_oracle_generator.py
python -m pytest tests/test_stage6_codex_execution.py tests/test_stage11_validation.py
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
python -m pytest
git diff --check
```

If the generator writes files, run it twice and confirm:

```powershell
git diff -- hidden_tests/cases_v2
```

after the second run is empty.

## Done Criteria

Stage 17 is complete when:

- A private v2 oracle exists and does not import starter implementation code.
- The v2 generator creates all required hidden categories.
- `hidden_tests/cases_v2/manifest.json` records the fixed seed, category
  weights, file hashes, case counts, and points.
- Regenerating v2 hidden cases twice with the same seed produces identical file
  contents and manifest hashes.
- The v2 oracle can produce expected outputs for every generated operation
  type.
- Every generated case references documented Stage 16 rule IDs.
- Category weights and points are visible in the manifest.
- Concrete hidden inputs and expected outputs remain outside implementation
  workspaces and measured prompts.
- Existing v1 hidden tests and harness tests continue to pass.

## Risks

Risk: The oracle accidentally mirrors starter bugs.

Mitigation: Keep the oracle independent from `benchmark_template_v2` and test
oracle edge cases directly.

Risk: Generated hidden cases leak into visible assets.

Mitigation: Keep all generated cases under `hidden_tests/cases_v2/`, extend
privacy validation, and avoid copying payloads into docs or prompts.

Risk: Stage 17 grows into the Stage 18 runner upgrade.

Mitigation: Generate operation payloads and expected outputs here, but keep
execution support changes minimal unless needed for validation.

Risk: Performance cases dominate runtime or scoring.

Mitigation: Use moderate deterministic cases, keep performance weights bounded,
and leave timeout enforcement details to Stage 18.

Risk: Category coverage is broad but shallow.

Mitigation: Require nonzero points per category plus targeted cases for every
major Stage 16 rule family.

## Open Questions

- Should v2 hidden operation names be version-prefixed, such as
  `v2_reduce_and_summarize`, to avoid ambiguity in the Stage 18 runner?
- Should `hidden_tests/cases_v2_placeholder/` remain as a tiny fixture for
  backward-compatible tests, or should tests migrate fully to
  `hidden_tests/cases_v2/`?
- Should the v2 manifest use `schema_version: 2`, or keep `schema_version: 1`
  to preserve the current `harness.hidden_runner.load_cases` assumptions?
- How much oracle direct testing should use small public-like fixtures versus
  generated hidden fixtures?
- Should performance cases include expected outputs in full, hashes of expected
  outputs, or both?
