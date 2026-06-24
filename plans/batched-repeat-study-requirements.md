# Batched Repeat Study Requirements

## Purpose

RuleLedger v3 paper-grade evidence can be accumulated across multiple batches.
For example, a study may run 20 repeats per reasoning level now and 30 more
later, then pool the 50 repeats per reasoning level. Pooling is only defensible
when the benchmark and measurement contract are frozen across batches, and when
batch-level metadata is preserved for drift checks.

## Frozen Fields

The following fields must stay identical for batches that will be pooled:

- Full study config hash.
- Full expanded matrix hash.
- Benchmark template tree hash.
- Hidden cases tree hash and hidden manifest hash.
- Prompt template hashes, including common, topology, judge, and output schema
  prompts.
- Scoring config hash and scoring semantics.
- Judge prompt, output schema, model, and reasoning setting.
- Implementation model identifiers and reasoning settings.
- Timeout policy.
- Rerun policy, failure handling, and full run matrix shape.
- Batch selection rule, meaning planned repeat ranges must be documented before
  pooling and must not overlap.
- Harness commit, or an explicit compatibility note showing that scoring and
  artifact semantics did not change.

The following fields may differ but must be recorded and analyzed:

- Batch ID and sequence.
- Batch start timestamp.
- Selected repeat range and selected matrix hash.
- Run order within the selected range.
- Codex/preflight metadata.
- Repository dirty-state hash at launch.
- Platform or model-service drift noticed by the operator.
- Operator notes.

## Batch Metadata Artifact

Each experiment directory writes `batch_metadata.json`. This file records:

- `study.id`: stable identifier for the pooled study.
- `batch.id`: stable identifier for one batch.
- `batch.sequence`: optional 1-based sequence number.
- `batch.notes`: operator notes.
- `pooling_requirements`: the frozen-field checklist.
- `freeze_manifest`: hashes and configuration facts needed to compare batches.

The freeze manifest includes repository state, config hash, full matrix hash,
selected matrix hash, benchmark metadata, template tree hash, hidden-cases tree
hash, hidden manifest hash, scoring config hash, prompt-template hashes, judge
output schema hash, model settings, judge settings, timeouts, and
failure-policy settings.

## Running Batches

Use explicit study and batch identifiers:

```powershell
.\scripts\run_experiment.ps1 `
  -Config configs\ruleledger_v3_paper_50.yaml `
  -ExperimentName v3_paper_batch_01 `
  -StudyId ruleledger_v3_reasoning_whitepaper `
  -BatchId v3-paper-batch-001 `
  -BatchSequence 1 `
  -RepeatFrom 1 `
  -RepeatTo 20 `
  -BatchNotes "first 20 repeats per reasoning level"
```

A later batch should use the same frozen commit and config, but a new batch ID:

```powershell
.\scripts\run_experiment.ps1 `
  -Config configs\ruleledger_v3_paper_50.yaml `
  -ExperimentName v3_paper_batch_02 `
  -StudyId ruleledger_v3_reasoning_whitepaper `
  -BatchId v3-paper-batch-002 `
  -BatchSequence 2 `
  -RepeatFrom 21 `
  -RepeatTo 50 `
  -BatchNotes "additional 30 repeats per reasoning level"
```

## Pooling Rule

Before combining batches, compare `batch_metadata.json` from every experiment
directory. Pool only when frozen-field hashes match. The selected matrix hashes
should differ between batches when the repeat ranges differ, but the selected
run IDs should be non-overlapping and should cover the intended repeat range.
If any frozen field differs, either exclude the batch from the pooled estimate
or report it as a separate cohort. If the order is consistent but a frozen field
changed, report that as supporting but not pooled evidence.

Paper or white-paper analysis should include both:

- pooled results across all eligible batches;
- per-batch results, so time or platform drift is visible.
