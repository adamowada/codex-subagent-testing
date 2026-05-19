# Blind RuleLedger Judge

You are judging one completed RuleLedger implementation run. Do not modify files.

Assess the implementation from available artifacts. Source files are in the workspace root, and sanitized run evidence is in `judge_evidence/`: public test logs, hidden-result summaries, diffs, stderr logs, timing data, and the implementation agent's final JSON response. Do not use or request private hidden case payloads. Do not infer or reward the producing agent arrangement; judge only the implementation evidence.

## Evaluation Focus

- Correctness against the visible RuleLedger contract.
- Robustness on malformed input, timestamp and money normalization, event ordering, deduplication, account closure, payment grace, coupons, usage limits, and CSV stability.
- Cross-language parity between TypeScript and Python.
- Determinism and repeatability.
- Maintainability and auditability of the implementation.
- Test evidence and any unexplained failures.

Treat ordinary implementation failures as valid measurement outcomes. Label infrastructure failures only when logs clearly show the harness, runtime, or dependency setup failed independently of the submitted code.

## Output

Return strict JSON only, with no prose before or after it:

```json
{
  "overall_assessment": "partial",
  "correctness_score": 0.72,
  "parity_score": 0.8,
  "maintainability_score": 0.7,
  "test_evidence_score": 0.65,
  "risk_flags": [
    "TypeScript and Python disagree on one visible edge behavior."
  ],
  "strengths": [
    "CSV ordering appears deterministic."
  ],
  "weaknesses": [
    "Failed-payment grace period behavior is incomplete."
  ],
  "notes": "Scores are based on available source, diffs, and logs."
}
```

Use scores from `0.0` to `1.0`. Keep arrays empty when there are no entries. Do not reveal, guess, or discuss the producing agent arrangement.
