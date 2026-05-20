# Stage 15: Create The V2 Starter Template

## Purpose

Stage 15 creates the real RuleLedger v2 starter template. It forks the current
v1 starter into a harder visible benchmark surface while preserving the same
public TypeScript and Python API names.

This stage should answer:

```text
Can measured agents start from a runnable v2 RuleLedger project that exposes
the hard-mode vocabulary and public examples without revealing hidden cases or
requiring a different API?
```

Stage 15 is about the starter project only. It should make v2 visible, runnable,
and intentionally incomplete. It should not fully specify every hidden rule,
build the private oracle, upgrade hidden runner operations, or recalibrate
scoring.

## Scope

Stage 15 owns:

- Forking the current v1 starter into a v2 benchmark template directory.
- Preserving existing TypeScript and Python public function names.
- Extending visible raw event fields with v2 hard-mode fields.
- Normalizing new fields into deterministic camelCase output shapes.
- Updating public README documentation for added fields and visible rule
  concepts.
- Updating public fixtures and public tests with small examples for major v2
  concepts.
- Keeping TypeScript and Python starter surfaces compatible.
- Ensuring the v2 starter passes public commands.
- Keeping the starter incomplete enough that hidden hard-mode tests remain
  meaningful.

Stage 15 does not own:

- Creating final v2 hidden cases.
- Implementing the private v2 oracle.
- Defining every hard-mode semantic edge case.
- Adding hidden runner v2 operations.
- Changing the default v1 experiment config.
- Changing scoring weights or cross-version report policy.
- Editing locked top-level source-of-truth documents.
- Committing generated run output under `runs/`.

## Inputs

Stage 15 starts from:

```text
benchmark_template/
configs/initial_experiment.yaml
tests/fixtures/stage14/
harness/
plans/stage-14-version-benchmark-assets.md
```

Stage 14 made the harness able to select a benchmark template by config. Stage
15 should replace or supersede the tiny synthetic v2 template fixture with a
real v2 starter path used by a v2 config. The final path can be chosen during
implementation, but it should be repository-relative and config-selected.

Recommended paths:

```text
benchmark_templates/ruleledger_v1/
benchmark_templates/ruleledger_v2/
```

or, if avoiding a v1 move is preferable:

```text
benchmark_template/
benchmark_template_v2/
```

The lower-risk choice is to add a new v2 directory and leave the existing v1
`benchmark_template/` untouched.

## Public API Contract

The TypeScript API should still live in `src/index.ts` and expose:

```text
parseEventLine
normalizeEvent
reduceAccountState
evaluateEntitlements
summarizeAccount
exportLedgerReport
```

The Python API should still live in `ruleledger/engine.py` and expose:

```text
parse_event_line
normalize_event
reduce_account_state
evaluate_entitlements
summarize_account
export_ledger_report
```

The functions may accept richer inputs and return richer output objects, but the
function vocabulary should not change. This preserves comparability with v1 and
lets existing prompt templates remain broadly useful.

## V2 Raw Event Fields

The v2 starter should document and visibly accept these raw event fields:

```text
effective_at
recorded_at
sequence
currency
quantity
seat_delta
merge_from_account_id
correction_of
voided_event_id
invoice_id
period_start
period_end
```

The starter implementation does not need to implement all final hard-mode
behavior. It should, however, expose the fields in validation and normalization
paths so agents see the target shape.

## Normalized Output Fields

Raw snake_case fields should normalize to deterministic camelCase output fields:

```text
effectiveAt
recordedAt
sequence
currency
quantity
seatDelta
mergeFromAccountId
correctionOf
voidedEventId
invoiceId
periodStart
periodEnd
```

The normalized event shape should remain compatible between TypeScript and
Python. If a field is omitted, output policy should be explicit:

- Required normalized fields should always be present.
- Optional fields should either be omitted consistently or represented as
  `null`/`None` consistently before JSON serialization.
- CSV exports should use empty strings for absent optional values when exposed.

Stage 16 may tighten these semantics, but Stage 15 should avoid ambiguous public
examples.

## Data Representation Rules

Money:

- Use integer minor units for all money values.
- Avoid floating point arithmetic in starter examples.
- Preserve existing decimal-string input examples where useful, but normalize to
  minor-unit integer outputs.
- Include currency in visible v2 examples where money appears.

Timestamps:

- Normalize timestamps to canonical ISO UTC strings.
- Use millisecond precision.
- Apply the same timestamp formatting in TypeScript and Python.
- Include examples where `timestamp`, `effective_at`, and `recorded_at` differ.

Ordering:

- Public docs should introduce the intended v2 replay order:

```text
(effectiveAt, recordedAt, sequence, id)
```

- Public tests should include at least one small ordering example.
- Full edge-case ordering semantics belong to Stage 16 and hidden cases.

## Starter Completeness Boundary

The v2 starter should be more informative than v1 but still incomplete.

It should likely implement or stub enough behavior to pass visible tests:

- Basic parsing and malformed JSON handling.
- Basic normalization of new v2 fields.
- Basic timestamp canonicalization.
- Basic integer minor-unit money conversion.
- One simple bitemporal ordering example.
- One simple correction or void example.
- One simple account merge field example.
- One simple billing-period or invoice field example.
- Basic TypeScript/Python parity for public fixtures.

It should not attempt to fully solve all future hidden categories:

- Deep bitemporal replay.
- Complex correction and void visibility.
- Full lifecycle precedence.
- Account merge state migration.
- Full billing proration.
- Large performance pipelines.
- Metamorphic invariants.
- Exhaustive CSV/reporting edge cases.

That incompleteness is important. If the starter already solves the hard-mode
benchmark, hidden tests lose calibration value.

## Public README Content

The v2 README should include:

- Setup commands.
- Public API names for TypeScript and Python.
- Raw event field reference, including v2 additions.
- Normalized field reference, including camelCase names.
- Timestamp normalization expectations.
- Money minor-unit expectations.
- Replay ordering summary.
- Short visible examples for:
  - Bitemporal timestamps.
  - Correction or void.
  - Account merge.
  - Seat or quantity change.
  - Billing period/invoice fields.
  - CSV/report parity.
- A clear note that public tests are visible guidance and not exhaustive.

The README should not include hidden case ids, hidden fixtures, generated hidden
expected outputs, or private oracle details.

## Public Fixtures And Tests

The v2 starter should include public fixture files analogous to v1, but updated
for v2. Suggested fixture paths:

```text
fixtures/public_events_v2.jsonl
fixtures/public_expected_summary_v2.json
fixtures/public_expected_report_v2.csv
```

Public TypeScript tests should cover:

- Parsing and normalization of all new v2 field names.
- Millisecond UTC timestamp normalization.
- Money minor units and currency.
- Bitemporal ordering for a tiny event set.
- Basic summary shape with v2 fields present.
- CSV output stability for a small fixture.

Public Python tests should cover the same concepts and use the same fixtures
where practical.

Parity checks should assert exact JSON-compatible output for shared fixtures
where possible. If exact object equality is too brittle for the starter, assert
the important common fields explicitly and leave stricter parity to hidden
tests.

## Configuration

Add a real v2 config that selects the real v2 starter template:

```text
configs/ruleledger_v2.yaml
```

or another clear name chosen during implementation.

The config should include:

- `benchmark.version`: `ruleledger_v2`.
- `paths.benchmark_template`: the new real v2 template path.
- `paths.hidden_cases`: a placeholder or synthetic v2 hidden case path until
  Stage 17 replaces it.
- `scoring.path`: a v2 or synthetic-v2 scoring profile path.
- A minimal cell matrix suitable for dry-run validation.

Do not change `configs/initial_experiment.yaml` default behavior away from v1.

## Hidden-Test Privacy

Stage 15 must not copy hidden cases into the v2 starter. The v2 public tests and
fixtures should be visible, small, and hand-authored.

Avoid names that collide with hidden case filenames. Avoid including hidden
payloads in README examples or public expected outputs.

The v2 starter may include public examples for concepts that hidden tests will
exercise, but the concrete hidden data remains private and generated later.

## Implementation Order

1. Choose the v2 template path and add it to config.
2. Copy the v1 starter into the v2 template path.
3. Update v2 package metadata and README.
4. Extend TypeScript types and starter normalization for v2 fields.
5. Extend Python parsing and starter normalization for v2 fields.
6. Add v2 public fixtures.
7. Add TypeScript public tests for v2 examples.
8. Add Python public tests for v2 examples.
9. Ensure both languages expose compatible public output shapes.
10. Add harness/config tests proving the v2 config selects the real v2 template.
11. Run public commands inside the v2 starter.
12. Run repository tests.

## Verification Commands

From the v2 starter template directory:

```powershell
npm ci
npm run typecheck
npm run test:public
python -m pytest -q tests_public_py
```

From the repository root:

```powershell
python -m pytest
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config <v2-config-path> --skip-preflight --allow-missing-report
.\scripts\run_experiment.ps1 -Config <v2-config-path> -DryRun -NoReport
```

Use an explicit temporary runs root for dry-runs if needed to avoid creating
repo-local generated outputs.

## Risks

Over-specifying Stage 16 semantics:

Stage 15 should introduce the public surface and examples, but avoid embedding a
complete hidden oracle in the starter.

Under-specifying visible behavior:

If public docs do not mention the new fields and representation rules, measured
agents may waste budget discovering basic vocabulary instead of solving hard
interactions.

Breaking v1:

The default v1 template and `configs/initial_experiment.yaml` should remain
runnable. V2 should be opt-in through config.

Cross-language drift:

TypeScript and Python examples should use shared fixtures wherever possible so
field naming, timestamp formatting, and money representation stay aligned.

Hidden leakage:

Public examples should be new, small, and visible by design. Do not copy hidden
generator output or hidden expected values into the starter.

Dependency churn:

Avoid new large dependencies. The starter should stay easy to copy, install, and
run inside measured worktrees.

## Done When

- A real v2 starter template exists at a config-selected repository-relative
  path.
- The existing v1 starter and default experiment config remain unchanged in
  behavior.
- The v2 starter README documents added event fields, normalized output fields,
  timestamp rules, money rules, ordering rules, and billing concepts.
- TypeScript and Python expose the same function names as v1.
- TypeScript and Python public tests cover every major hard-mode concept with
  small visible examples.
- In the v2 starter, `npm run typecheck`, `npm run test:public`, and
  `python -m pytest -q tests_public_py` pass.
- The starter remains intentionally incomplete against future hidden hard-mode
  categories.
- Repository-level tests pass.
- Static validation passes for v1 and the v2 config.
- No hidden cases or generated run outputs are committed.
