# Solo Topology Instructions

This is a solo implementation run. Work as one implementer.

Do not spawn subagents, delegate to workers, start helper agent processes, call external AI, or invoke nested Codex commands. The comparison baseline depends on this run staying genuinely solo.

## Priorities

- Read the visible source, README, fixtures, and public tests before editing.
- Implement TypeScript and Python together so behavior stays aligned.
- Preserve the public APIs exactly.
- Prefer deterministic validation and reduction over case-specific fixes.
- Keep constants and state transitions easy to audit.
- Run the visible TypeScript and Python checks when practical.

Focus on correctness, hidden-test robustness, maintainability, and cross-language parity. Public tests are intentionally incomplete, so use the full visible RuleLedger contract from the shared instructions.
