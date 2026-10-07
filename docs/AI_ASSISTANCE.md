# AI assistance and study notes

The spec permits AI-written code. Codex generated this implementation, tests,
deployment configuration, and documentation. It read the spec, implemented DAGs
and scheduling, added API/interface/accounts/storage, and ran verification.
Official Render documentation informed the persistent-disk configuration.

This does not establish that the student independently reviewed or understood
the code. No student reflection, manual browser outcome, or remote deployment
result is claimed. The student should review the implementation and add their own
lessons learned after using and deploying it.

## Details to understand

- Trace `generate_dc(2,2,1,2,3,4)`: why does the combine wait for both leaves,
  why is work 12, and why is span 9?
- Trace time 3 for `[3,3,2,2,2]` on two processors: why process simultaneous
  completions together before selecting ready tasks?
- Explain the reverse-topological rank recurrence and why Map ranks equal durations.
- Explain the makespan-7 heuristic schedule and a makespan-6 alternative partition.
- Follow a run from `fetch` through validation/generation/scheduling to aligned SVG rows.
- Follow hashing, session identity, CSRF rotation, and ownership checks.
- Replay create/rename/delete events and explain transaction locks and `fsync`.
- Explain the distinct roles of a persistent disk (records) and stable secret (sessions).

## Engineering observations

A lower bound is not always attainable by a heuristic. Numeric tie-breaking and
simultaneous completions need explicit tests. Equivalent JSON objects can have
different key orders, so serialization alone is a fragile equality test. File
appends need concurrency/crash handling. DOM integration tests check behavior,
while layout/native focus need a browser. Hosted persistence requires testing the
actual disk arrangement. These notes supplement the student's own review rather
than replacing it.
