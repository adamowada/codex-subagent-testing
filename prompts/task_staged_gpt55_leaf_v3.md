# Staged GPT-5.5 Leaf V3 Topology Instructions

You are participating in an outer-harness staged GPT-5.5 leaf experiment for
RuleLedger v3.

Current write mode: `{{ spark_mode }}`

The harness, not this Codex process, invokes the GPT-5.5 root planning run,
{{ leaf_count }} GPT-5.5 leaf runs, and the GPT-5.5 root integration run as
separate measured processes. Do not spawn subagents, invoke `codex`, call
external AI, or start other agent processes from inside any measured process.

## Required GPT-5.5 Leaves

The outer harness assigns exactly {{ leaf_count }} GPT-5.5 worker leaves using
the `{{ leaf_assignment_set }}` assignment set:

{{ staged_leaf_assignments }}

## Mode Rules

Direct edit mode gives each leaf an isolated writable copy of the starter
workspace. The root integration run receives leaf diffs and decides what to
apply to the measured final workspace.

Proposal mode gives each leaf a read-only workspace. The root integration run
receives leaf proposals and decides what to implement in the measured final
workspace.

The final measured implementation is whatever the GPT-5.5 root integration run
lands in the final workspace. Leaf outputs are evidence and advice, not
automatically accepted truth.
