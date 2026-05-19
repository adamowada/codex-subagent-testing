# Stage 4 Plan: Prompts And Agent Configs

## Goal

Create the reusable implementation prompts, judge prompt, and Codex agent configuration templates needed to turn the expanded experiment matrix into measured Codex runs.

Stage 4 is complete when every expanded run record from `configs/initial_experiment.yaml` can render:

- One implementation prompt made from shared RuleLedger instructions plus the topology-specific prompt.
- One Codex config directory or config file with the correct root, sublead, and leaf agent settings.
- One judge prompt that can evaluate a completed run without knowing which topology produced it.

The prompts and configs are part of the measurement apparatus. They should be deterministic, auditable, and careful about isolation so that C0-C4 measure the intended agent topologies instead of prompt ambiguity.

## Non-Goals

- Do not implement the full experiment orchestrator in this stage.
- Do not run measured Codex implementation jobs.
- Do not run judge jobs against real experiment outputs.
- Do not generate final reports or aggregate scores.
- Do not include hidden case data, hidden expected outputs, private scoring examples, or private fixture payloads in prompts.
- Do not copy hidden tests into prompt files, rendered prompts, starter projects, or run worktrees.
- Do not edit locked top-level source-of-truth documents unless explicitly requested.
- Do not add generated run output under `runs/`.

## Target Directory Layout

```text
prompts/
  task_common.md
  task_solo.md
  task_flat_spark.md
  task_depth2_subleads.md
  judge.md

codex_templates/
  config.toml.j2
  agents/
    spark_direct_implementer.md
    spark_proposal_implementer.md
    spark_direct_tester.md
    spark_proposal_tester.md
    spark_adversary.md
    gpt55_medium_sublead.md

harness/
  prompt_rendering.py

tests/
  test_prompt_rendering.py
```

The `agents/` snippet files are optional if `config.toml.j2` remains readable without them. Prefer snippet files if the role instructions become long enough that the TOML template is hard to audit.

## Inputs From Earlier Stages

Stage 4 consumes these existing artifacts:

- `benchmark_template/README.md` for the visible RuleLedger task description.
- `benchmark_template/src/index.ts` for TypeScript exported types and function names.
- `benchmark_template/ruleledger/engine.py` for Python exported names and docstrings.
- `benchmark_template/tests_public_ts/` and `benchmark_template/tests_public_py/` for public test expectations.
- `configs/initial_experiment.yaml` for prompt template paths, model choices, reasoning levels, Spark modes, depth, and thread settings.
- `harness.matrix.expand_experiment_matrix` for deterministic run records.

Stage 4 must not consume hidden case data except for high-level isolation requirements already documented in repository plans.

## Prompt Rendering Contract

Implementation prompts should be rendered by combining:

1. `prompts/task_common.md`
2. The topology prompt referenced by the run record:
   - `task_solo.md`
   - `task_flat_spark.md`
   - `task_depth2_subleads.md`

The rendered implementation prompt should include a small run metadata block derived from the run record, such as:

```text
run_id: C1_direct_r03
cell_id: C1
topology: flat_spark
spark_mode: direct
root_model: gpt-5.5
root_reasoning: medium
agents_max_depth: 1
agents_max_threads: 8
```

The metadata is for reproducibility and diagnostics. It should not include hidden test details or private scoring examples.

The renderer should support deterministic output. Rendering the same run twice with the same template files and config should produce byte-identical prompt text.

## Template Variable Contract

`harness.prompt_rendering` should accept one expanded run record and expose a small, explicit template context. Recommended keys:

- `run_id`
- `cell_id`
- `cell_name`
- `topology`
- `spark_mode`
- `spark_mode_name`
- `proposal_only`
- `leaf_write_mode`
- `root_model`
- `root_reasoning`
- `sublead_model`
- `sublead_reasoning`
- `sublead_count`
- `leaves_per_sublead`
- `leaf_model`
- `leaf_count`
- `spark_reasoning_implementer`
- `spark_reasoning_tester`
- `spark_reasoning_adversary`
- `agents_max_depth`
- `agents_max_threads`
- `implementation_timeout_seconds`
- `judge_model`
- `judge_reasoning`
- `judge_sandbox`

For C0, leaf and sublead values should render as explicit empty values such as `none`, not as missing-template errors.

Prefer a narrow rendering API over passing the entire config object into templates. This keeps prompts stable and prevents accidental leakage of fields that are not meant for measured agents.

## Shared Prompt: `task_common.md`

`task_common.md` is the full shared RuleLedger contract. It should be included in every measured implementation prompt.

It must cover:

- RuleLedger purpose and domain.
- Public TypeScript API.
- Public Python API.
- Required behavior.
- Public commands.
- Public test expectations.
- Cross-language parity requirement.
- Determinism and reproducibility requirements.
- Constraints on dependencies and generated files.
- Prohibition on nested Codex, nested agents outside the configured topology, external AI calls, and AI service calls.
- Final response JSON schema.

### TypeScript API

The prompt should name the TypeScript exports in `src/index.ts`:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`

The prompt should tell measured agents to preserve the exported API unless a public test or visible source contract requires otherwise.

### Python API

The prompt should name the Python exports in `ruleledger/engine.py`:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

The prompt should tell measured agents to preserve idiomatic Python naming while keeping behavior equivalent to TypeScript.

### Visible Behavior

The shared prompt should restate only visible benchmark behavior:

- Parse newline-delimited JSON subscription events.
- Reject malformed JSON, empty lines, and non-object JSON without throwing.
- Trim required string fields.
- Reject missing or whitespace-only IDs.
- Reject invalid event types and plans.
- Normalize timestamps to deterministic ISO UTC strings.
- Reject invalid timestamps.
- Convert decimal money strings to integer cents.
- Reject invalid money fields, including ambiguous precision.
- Sort events deterministically by timestamp and event ID.
- Deduplicate event IDs after sorting.
- Handle out-of-order input.
- Apply plan prices, feature sets, and usage limits.
- Apply coupons and coupon expiration behavior.
- Apply failed-payment grace periods.
- Ensure closed accounts override otherwise-active entitlements.
- Produce deterministic account summaries.
- Export deterministic CSV with stable headers, row ordering, booleans, missing-date behavior, and trailing newline.
- Preserve parity between TypeScript and Python for shared fixtures.

### Public Commands

The prompt should list visible commands exactly as the benchmark template exposes them:

```powershell
npm run typecheck
npm run test:public
python -m unittest discover -s tests_public_py
```

The prompt should make clear that public tests are useful guidance but intentionally incomplete.

### Nested-Agent Prohibition

Every implementation prompt must include a prominent rule:

- Do not invoke `codex`, `codex exec`, or any nested Codex process from inside the measured run.
- Do not call external AI services.
- Do not start another AI agent process.
- Use only the subagents made available by the configured Codex run, and only when the topology prompt allows it.

This rule should appear in `task_common.md`, and topology prompts should reinforce it where needed.

### Final Response JSON Schema

The implementation agent should finish with strict JSON so the harness can parse the final response. Recommended schema:

```json
{
  "status": "success",
  "summary": "Implemented RuleLedger behavior in TypeScript and Python.",
  "changed_files": [
    "src/index.ts",
    "ruleledger/engine.py"
  ],
  "tests_run": [
    {
      "command": "npm run typecheck",
      "status": "passed",
      "notes": ""
    },
    {
      "command": "npm run test:public",
      "status": "passed",
      "notes": ""
    },
    {
      "command": "python -m unittest discover -s tests_public_py",
      "status": "passed",
      "notes": ""
    }
  ],
  "known_issues": [],
  "nested_codex_invoked": false
}
```

Allowed `status` values should be:

- `success`
- `partial`
- `failed`

Allowed test statuses should be:

- `passed`
- `failed`
- `not_run`

The schema should be prompt-level guidance. The later orchestrator should still tolerate malformed final responses and preserve raw evidence.

## Solo Prompt: `task_solo.md`

`task_solo.md` is used only by C0.

It must:

- Explicitly forbid subagents.
- Tell the root agent to work as a single implementer.
- Emphasize correctness, hidden-test robustness, deterministic behavior, parity, and maintainability.
- Encourage reading visible source and public tests before editing.
- Encourage running public TypeScript and Python checks before final response.
- Avoid any role decomposition language that could make C0 behave like a multi-agent topology.

Recommended C0 guidance:

- Implement both languages in a coordinated way.
- Keep behavior aligned by comparing equivalent fixtures.
- Prefer explicit constants and clear state transitions.
- Avoid speculative dependencies.
- Preserve the public API.

## Flat Spark Prompt: `task_flat_spark.md`

`task_flat_spark.md` is used by C1-C3.

It must instruct the GPT-5.5 root lead to coordinate six Spark leaves:

1. TypeScript parser and normalizer.
2. TypeScript reducer, entitlements, and report.
3. Python parser and normalizer.
4. Python reducer, entitlements, and report.
5. Cross-language fixture and public-test writer.
6. Adversarial reviewer.

The root lead owns final integration, conflict resolution, test execution, and final response JSON. Spark leaves are helpers, not independent final authorities.

### Direct Mode

When `spark_mode` is `direct`:

- Implementer leaves may edit their assigned implementation files.
- Tester leaves may edit public tests or shared visible fixtures if that is part of their role.
- The adversarial reviewer remains read-only.
- The root lead should inspect and integrate leaf changes before final testing.
- Leaves should respect ownership boundaries to reduce conflicts.

### Proposal Mode

When `spark_mode` is `proposal`:

- Spark leaves are read-only.
- Leaves should return proposed patches, findings, test ideas, and risk notes.
- The root lead applies any accepted edits.
- The root lead remains responsible for final code changes and tests.

The prompt must make direct versus proposal behavior unmistakable because these modes are a primary experiment comparison.

### Flat Role Details

TypeScript parser and normalizer:

- Owns JSONL parsing and normalization behavior in `src/index.ts`.
- Focuses on validation, timestamp normalization, money conversion, string trimming, event type validation, and plan validation.

TypeScript reducer, entitlements, and report:

- Owns TypeScript state reduction, entitlement logic, account summaries, and CSV export.
- Focuses on sorting, deduplication, plan behavior, coupons, usage limits, failed-payment grace, closure override, and deterministic reporting.

Python parser and normalizer:

- Owns parsing and normalization behavior in `ruleledger/engine.py`.
- Keeps Python semantics aligned with TypeScript.

Python reducer, entitlements, and report:

- Owns Python state reduction, entitlement logic, account summaries, and CSV export.
- Keeps output shape and edge behavior aligned with TypeScript.

Cross-language fixture and public-test writer:

- Adds or improves visible tests and fixtures only when useful.
- Checks parity between TypeScript and Python on shared visible examples.
- Does not introduce hidden-test data.

Adversarial reviewer:

- Reviews for edge cases, nondeterminism, parity drift, incomplete validation, report instability, and brittle assumptions.
- Does not edit files.
- Provides concise findings for the root lead.

## Depth-2 Prompt: `task_depth2_subleads.md`

`task_depth2_subleads.md` is used by C4.

It must instruct the GPT-5.5 xhigh root lead to delegate to three GPT-5.5 medium subleads:

- Sublead A: TypeScript implementation.
- Sublead B: Python implementation.
- Sublead C: parity, fixtures, public tests, integration risk, and adversarial review.

Each sublead delegates to six Spark xhigh leaves. Spark leaves remain leaves; they should not spawn further subagents.

### Root Lead Responsibilities

The root lead should:

- Establish the implementation strategy.
- Assign work to subleads.
- Keep sublead scopes distinct.
- Track direct versus proposal mode.
- Integrate the final result.
- Resolve parity disagreements.
- Run public tests.
- Produce the final strict JSON response.

### Sublead A: TypeScript

Sublead A owns TypeScript work in `src/index.ts` and related visible TypeScript tests or fixtures.

Its Spark leaves should cover:

- Parsing and validation.
- Timestamp and money normalization.
- State reduction.
- Entitlements.
- CSV reporting.
- TypeScript-specific review or tests.

### Sublead B: Python

Sublead B owns Python work in `ruleledger/engine.py` and related visible Python tests or fixtures.

Its Spark leaves should cover:

- Parsing and validation.
- Timestamp and money normalization.
- State reduction.
- Entitlements.
- CSV reporting.
- Python-specific review or tests.

### Sublead C: Parity And Risk

Sublead C owns cross-language consistency and integration risk.

Its Spark leaves should cover:

- Shared fixture design.
- Public test improvements.
- TypeScript/Python parity checks.
- Determinism review.
- CSV/reporting review.
- Adversarial review.

### C4 Direct And Proposal Modes

The C4 prompt must preserve the same direct/proposal semantics as the flat prompt:

- In direct mode, direct implementer and tester leaves may edit within their assigned scope.
- In proposal mode, Spark leaves are read-only and subleads/root apply accepted changes.
- Adversarial leaves are always read-only.
- Subleads should not override changes outside their ownership without coordinating through the root.

C4 is an intentional stress test. The prompt should acknowledge the larger topology without apologizing for it or weakening the measurement.

## Judge Prompt: `judge.md`

`judge.md` is used by the blind GPT-5.5 xhigh judge after implementation and tests.

It must:

- Avoid revealing the producing topology, cell, Spark mode, or model mix.
- State that the judge must not modify files.
- Instruct the judge to inspect source, public test logs, hidden result summaries, diffs, stderr logs, final response JSON, and any preserved metadata that does not reveal topology.
- Ask for strict JSON output.
- Score evidence, not style preferences.
- Treat failures as part of the experiment, not infrastructure surprises, unless logs indicate harness failure.

Recommended judge output schema:

```json
{
  "overall_assessment": "partial",
  "correctness_score": 0.72,
  "parity_score": 0.8,
  "maintainability_score": 0.7,
  "test_evidence_score": 0.65,
  "risk_flags": [
    "Python and TypeScript disagree on coupon expiration boundaries."
  ],
  "strengths": [
    "Deterministic CSV ordering appears stable."
  ],
  "weaknesses": [
    "Failed-payment grace period coverage is incomplete."
  ],
  "notes": "Scores are based on available source, diffs, and logs."
}
```

The exact score names can change later if Stage 8 scoring requires a different schema, but the prompt should be strict and machine-readable from the start.

## Codex Config Template

`codex_templates/config.toml.j2` should render the Codex agent configuration for each implementation run.

The template should represent:

- Root model.
- Root reasoning effort.
- `agents.max_depth`.
- `agents.max_threads`.
- Allowed custom agent roles.
- Per-role model.
- Per-role reasoning effort.
- Per-role sandbox or write mode.
- Per-role instructions.

The exact TOML section names should be verified against the Codex config schema during implementation. The rendered behavior must match the run record and the command-line overrides that Stage 6 will use.

## Required Agent Templates

Stage 4 should define these custom agent templates.

### Spark Direct Implementer

- Model: `gpt-5.3-codex-spark`.
- Reasoning: role-specific Spark reasoning, initially `xhigh`.
- Sandbox: `workspace-write`.
- Purpose: implement assigned code directly.
- Must stay within assigned files and responsibilities.
- Must not spawn agents or invoke Codex.

### Spark Proposal Implementer

- Model: `gpt-5.3-codex-spark`.
- Reasoning: role-specific Spark reasoning, initially `xhigh`.
- Sandbox: `read-only`.
- Purpose: inspect code and propose changes.
- Must return actionable patches or precise guidance.
- Must not edit files.
- Must not spawn agents or invoke Codex.

### Spark Tester Direct

- Model: `gpt-5.3-codex-spark`.
- Reasoning: tester Spark reasoning, initially `xhigh`.
- Sandbox: `workspace-write`.
- Purpose: add or adjust visible tests and fixtures within assigned scope.
- Must not add hidden data.
- Must not make implementation edits unless explicitly assigned by the root or sublead.

### Spark Tester Proposal

- Model: `gpt-5.3-codex-spark`.
- Reasoning: tester Spark reasoning, initially `xhigh`.
- Sandbox: `read-only`.
- Purpose: propose test cases, fixture improvements, and parity checks.
- Must not edit files.

### Spark Adversary

- Model: `gpt-5.3-codex-spark`.
- Reasoning: adversary Spark reasoning, initially `xhigh`.
- Sandbox: `read-only`.
- Purpose: find flaws, edge cases, nondeterminism, incomplete validation, and parity risks.
- Must not edit files.
- Must report concise, actionable findings.

### GPT-5.5 Medium Sublead

- Model: `gpt-5.5`.
- Reasoning: `medium`.
- Sandbox: should follow the run's coordination needs and Codex config support.
- Purpose: coordinate a bounded C4 ownership area and manage Spark leaves.
- Must not invoke external AI or nested Codex commands.
- Must report results to the root lead.

## Direct Versus Proposal Validation

Rendered config and prompts should agree on write mode.

For `direct` runs:

- Spark direct implementer sandbox is `workspace-write`.
- Spark direct tester sandbox is `workspace-write`.
- Spark adversary sandbox is `read-only`.
- Prompt text says implementer/tester leaves may edit assigned files.

For `proposal` runs:

- Spark proposal implementer sandbox is `read-only`.
- Spark proposal tester sandbox is `read-only`.
- Spark adversary sandbox is `read-only`.
- Prompt text says Spark leaves must not edit files.

For C0:

- No subagent roles should be available or encouraged.
- `agents.max_depth` is `0`.
- `agents.max_threads` is `1`.
- The solo prompt forbids delegation.

For C4:

- `agents.max_depth` is `2`.
- `agents.max_threads` is at least `24`.
- Three subleads are described.
- Eighteen Spark leaves are described as leaves only.

## `harness.prompt_rendering`

Add a small helper module to make Stage 5 orchestration simpler.

Recommended functions:

```python
def render_implementation_prompt(run: Mapping[str, Any], repo_root: Path) -> str:
    ...

def render_judge_prompt(run: Mapping[str, Any], repo_root: Path) -> str:
    ...

def render_codex_config(run: Mapping[str, Any], repo_root: Path) -> dict[str, str]:
    ...
```

The config renderer can return a mapping of relative output paths to file contents, so the later orchestrator can write them into each run directory without Stage 4 needing to create run outputs.

The module should:

- Resolve paths relative to the repository root.
- Fail clearly on missing template files.
- Fail clearly on missing required run-record fields.
- Normalize newlines for deterministic output.
- Keep hidden-test data out of rendered prompts.
- Avoid hard-coding cell-specific logic that already exists in config.

If Jinja2 is used for `.j2` rendering, add the smallest reasonable dependency path and document it. If avoiding dependencies is preferred, keep placeholders simple enough for a small standard-library renderer and consider renaming the template if `.j2` is misleading.

## Prompt Quality Rules

Prompts should be:

- Specific enough to produce comparable behavior across repeats.
- Stable enough that later report artifacts can cite prompt versions.
- Short enough that important rules are not buried.
- Explicit about topology and role responsibilities.
- Explicit about public commands and final JSON output.
- Explicit that hidden tests exist but hidden data is unavailable.
- Free of private fixture payloads and private expected outputs.
- Free of instructions to modify repository-level harness files during measured implementation.

Avoid putting scoring weights in implementation prompts unless they are already public and intentionally visible. The measured agents should solve the benchmark contract, not optimize against private scoring internals.

## Reproducibility Requirements

Stage 4 should make it possible for Stage 5 and Stage 6 to preserve:

- Rendered implementation prompt as `rendered_prompt.md`.
- Rendered judge prompt or judge prompt reference.
- Rendered Codex config under `codex_config/`.
- Prompt template paths and content hashes in `metadata.json`.
- Config template path and content hash in `metadata.json`.

Hashing can be implemented later, but prompt and config files should be structured so hashing them is meaningful.

## Security And Isolation Requirements

Implementation prompts and agent configs must preserve benchmark isolation:

- Do not expose `hidden_tests/cases/` payloads.
- Do not paste oracle behavior from hidden generators into prompts.
- Do not instruct agents to inspect repository-level hidden tests.
- Do not allow measured agents to call Codex recursively.
- Do not allow measured agents to use external AI services.
- Do not grant write access to read-only proposal or adversary roles.
- Do not let Spark leaves spawn more agents.

The judge prompt may reference hidden result summaries produced by the harness, but it should not need raw hidden case payloads.

## Testing Plan

Add tests in `tests/test_prompt_rendering.py`.

Recommended coverage:

- All configured prompt template paths exist.
- The config template path exists.
- Rendering succeeds for all 45 expanded run records.
- Rendering is deterministic for a representative run.
- C0 rendered prompt contains solo instructions and no subagent assignment list.
- C1-C3 rendered prompts contain the six flat Spark roles.
- C4 rendered prompt contains the three sublead ownership areas.
- Direct-mode prompts mention assigned-file editing for allowed Spark roles.
- Proposal-mode prompts state that Spark leaves are read-only.
- Every implementation prompt contains the nested Codex prohibition.
- Every implementation prompt contains the final response JSON schema instruction.
- Judge prompt does not contain topology names such as `C0`, `C1`, `flat_spark`, or `depth2_subleads`.
- Rendered configs use Spark xhigh for leaf roles.
- Rendered configs use GPT-5.5 medium for C4 subleads.
- Rendered configs use `workspace-write` for direct implementer/tester roles.
- Rendered configs use `read-only` for proposal and adversary roles.

Add a repository scan test or helper that fails if prompt files contain obvious hidden case file paths such as:

- `hidden_tests/cases/parse_validation.json`
- `hidden_tests/cases/normalization.json`
- `hidden_tests/cases/state_reduction.json`
- `hidden_tests/cases/reporting.json`
- `hidden_tests/cases/immutability.json`
- `hidden_tests/cases/parity.json`

The scan should focus on preventing accidental leakage of hidden artifacts, not banning ordinary references to hidden tests as an abstract concept.

## Implementation Steps

1. Create `prompts/`.
2. Write `task_common.md` from the visible RuleLedger contract.
3. Write `task_solo.md` for C0.
4. Write `task_flat_spark.md` for C1-C3 with direct/proposal branching text.
5. Write `task_depth2_subleads.md` for C4 with root, sublead, and leaf responsibilities.
6. Write `judge.md` with blind strict-JSON evaluation instructions.
7. Create `codex_templates/`.
8. Write `config.toml.j2`.
9. Add agent instruction snippets under `codex_templates/agents/` if useful.
10. Add `harness.prompt_rendering`.
11. Add prompt/config rendering tests.
12. Run the unit test suite.
13. Manually inspect one representative prompt for C0, C1 direct, C1 proposal, C4 direct, C4 proposal, and judge.
14. Confirm no hidden case payloads or private expected outputs appear in prompts or config templates.

## Acceptance Checklist

- `prompts/task_common.md` exists and describes the full visible RuleLedger contract.
- `prompts/task_solo.md` exists and forbids subagents.
- `prompts/task_flat_spark.md` exists and defines the six flat Spark roles.
- `prompts/task_depth2_subleads.md` exists and defines the C4 root/sublead/leaf topology.
- `prompts/judge.md` exists and keeps the judge blind to topology.
- `codex_templates/config.toml.j2` exists.
- Custom agent roles render the configured model, reasoning, sandbox, and role instructions.
- Direct and proposal modes are clearly distinguished in both prompts and config.
- Nested Codex and external AI invocation are prohibited in measured implementation prompts.
- Hidden case data is absent from prompt and config templates.
- Prompt rendering succeeds for all 45 expanded implementation runs.
- Rendered judge prompt produces strict JSON instructions and does not reveal topology.
- Unit tests verify the key rendering and isolation properties.

## Risks And Mitigations

Risk: Prompt text leaks hidden-test specifics.

Mitigation: Source prompts only from visible benchmark files and high-level public plans. Add scans for hidden case file paths and avoid copying oracle details.

Risk: Direct and proposal modes blur together.

Mitigation: Put mode-specific instructions in both the prompt and rendered agent config, then test representative direct and proposal runs.

Risk: C0 accidentally gets subagent capabilities.

Mitigation: Test C0 rendered prompt and config for solo-only behavior, `max_depth = 0`, and `max_threads = 1`.

Risk: C4 becomes too vague for useful coordination.

Mitigation: Define explicit sublead ownership and repeat the rule that Spark leaves are leaves only.

Risk: Codex config syntax drifts from the local Codex implementation.

Mitigation: Keep the template isolated, write rendering tests, and verify syntax during Stage 6 preflight before measured runs begin.

Risk: Final response JSON is malformed.

Mitigation: Make the schema simple and prominent. The later orchestrator should still preserve malformed output as raw evidence.

## Handoff To Later Stages

Stage 5 should use `harness.prompt_rendering` to write per-run artifacts:

- `rendered_prompt.md`
- `codex_config/`
- judge prompt or judge prompt reference

Stage 6 should execute Codex using those artifacts and command-line settings from each run record.

Stage 7 should preserve rendered prompts and configs as raw evidence.

Stage 8 should parse final response JSON when possible, but should treat malformed responses as measurable run outcomes rather than lost data.
