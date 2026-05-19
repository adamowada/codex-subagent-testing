# Hidden Tests

This directory contains the private RuleLedger hidden-test suite for Stage 2.

Hidden cases are intentionally kept outside `benchmark_template/`, prompts, and run worktrees. The harness should read these files from the repository checkout and execute them against a copied implementation workspace without copying hidden inputs or expected outputs into that workspace.

## Regeneration

Cases are generated deterministically:

```powershell
python hidden_tests/generators/generate_cases.py
```

The generator records its seed and case-file hashes in `cases/manifest.json`. Do not regenerate cases during measured runs. Regeneration should be an explicit benchmark revision.

## Privacy Rules

- Do not paste hidden case payloads into implementation prompts.
- Do not copy `hidden_tests/` into measured worktrees.
- Do not include full hidden inputs or expected outputs in run artifacts.
- Keep hidden-run result files limited to opaque case IDs, categories, scores, and short failure reason codes.
