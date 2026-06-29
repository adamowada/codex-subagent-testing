# GPT-5.5 Direct-Edit Quality Frontier

## Objective

Measure whether a staged direct-edit topology using GPT-5.5 leaves can improve
the RuleLedger v3 quality frontier over solo GPT-5.5 and prior Spark-assisted
direct-edit results.

The primary question is quality, not full factorial completeness. The matrix
therefore focuses on high and xhigh reasoning for both the root integrator and
the direct-edit leaves.

## Matrix

| Cell | Root model | Root reasoning | Leaf model | Leaf reasoning | Mode | Runs |
| --- | --- | --- | --- | --- | --- | ---: |
| GQF0 | GPT-5.5 | high | GPT-5.5 | high | direct edit | 20 |
| GQF1 | GPT-5.5 | xhigh | GPT-5.5 | high | direct edit | 20 |
| GQF2 | GPT-5.5 | high | GPT-5.5 | xhigh | direct edit | 20 |
| GQF3 | GPT-5.5 | xhigh | GPT-5.5 | xhigh | direct edit | 20 |

## Pilot

Run one repeat per cell before launching the full 80-run study:

```powershell
.\scripts\run_experiment.ps1 -Config configs/gpt55_direct_quality_frontier_pilot.yaml -Jobs 2 -JudgeJobs 2
```

The pilot should verify:

- Generic GPT-5.5 leaf prompt wording.
- Four staged runs complete and preserve artifacts.
- Role-level token fields populate when staged JSONL role annotations exist.
- Public tests, hidden tests, judge, usage parsing, scoring, HTML, and PDF report generation complete.

## Full Run

After a clean pilot:

```powershell
.\scripts\run_experiment.ps1 -Config configs/gpt55_direct_quality_frontier.yaml -Jobs 3 -JudgeJobs 3
```

Operator overrides for `-Jobs` and `-JudgeJobs` are expected if quota, wall
time, or local load suggests a slower or faster batch.

## Comparisons

- Same-root solo high and solo xhigh RuleLedger v3 baselines.
- Prior Spark high direct and Spark xhigh direct cells.
- Mean quality, median quality, variance, and failure rate.
- Frontier behavior: max score, top-quartile mean, and probability of beating
  solo xhigh.
- Total implementation tokens, GPT-5.5 implementation tokens, root tokens,
  leaf tokens, and quality per total implementation token.

## Expected Reads

- `xhigh` root plus `xhigh` leaves is the raw quality ceiling candidate.
- `xhigh` root plus `high` leaves may be the most practical high-quality cell.
- `high` root plus `xhigh` leaves is the bottleneck diagnostic: strong results
  imply leaf implementation strength matters more; weaker results imply root
  integration is the limiter.
- `high` root plus `high` leaves is the economical direct-edit team baseline.
