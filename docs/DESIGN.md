# Design decisions

## Model and generation

Fixed positive integer durations, identical processors, one processor per task,
no preemption, and zero communication/launch overhead. Time is simulated; tasks
do not execute user code, threads, or real waiting.

The only accepted forms are Map and D&C. Map uses 2–16 independent tasks with
durations 1–20; its final join has no cost or extra computation task. D&C uses
`2 ≤ n ≤ 8`, `2 ≤ k ≤ 8`, `1 ≤ b < n`, and independent split/base/combine costs
of 1–20. Backend validation rejects booleans, fractions, unsupported forms or
policies, missing parameters, and out-of-range values. The UI mirrors these limits.

Splitting uses `small = min((m+k-1)//k, m//2)`, `large = m-small`, implementing
the specified balanced rounding with integer arithmetic. Both children are
positive and smaller than their parent, so recursion terminates at b ≥ 1.
Numeric IDs are deterministic preorder: split, the entire left computation,
the entire right computation, then combine. A split precedes both child entries;
a combine waits for both child terminal tasks. No user-defined edges are accepted.

A binary recursion tree with L leaves has L−1 internal calls, hence
`N = L + 2(L−1) = 3L−2 ≤ 22` because L ≤ n ≤ 8. The generator explicitly enforces
the cap as well. Both forms require integer `1 ≤ P < N`; there are no display
markers counted as computation tasks.

## Scheduling and metrics

Kahn's algorithm detects missing dependencies, duplicate IDs/edges, and cycles.
Reverse topological traversal computes
`rank(v) = duration(v) + max(rank(successor))`. Span is the largest rank.

The simulator holds an unstarted-task map, completed-task set, available-processor
heap, and running-task heap of `(finish, processor, task)`. These collections
encode task status and current processor assignments. At each event, **every**
simultaneous completion is removed before readiness is recomputed. Ready tasks
are ordered, idle processors are filled, and time jumps to the next completion.
Unfinished work with no running/ready tasks is a structural error.

Priority keys are `(ID)`, `(-duration, ID)`, and `(-rank, ID)`. Processors are
allocated by ascending ID. There is no randomness or intentional idle time when
ready work exists. These policies are heuristics, not exact optimization.
Scanning the remaining tasks at each event is simple for N ≤ 22; scheduling is
approximately `O(N² log N)` with `O(N+E)` memory.

Backend metrics remain unrounded: W, S, W/S, completion T, W/T, W/(P×T), and
`max(W/P,S)`. The UI rounds only for display. Idle intervals complement task
assignments on each processor over `[0,T]`, including trailing idle time.

All policies use one validated graph. Saving sends only configuration and name;
the backend recomputes results and ignores submitted graphs, schedules, metrics,
and owner IDs. Loading restores the stored configuration and results.

## Interface

One timeline SVG contains every processor row on a shared scale:
`x(t) = left + t/T × width`. Shared ticks/row extents align concurrency. Idle
segments are hatched. Horizontal scrolling preserves readability on small
screens. The supporting DAG uses topological layers and is collapsed by default;
collapsing it leaves the timeline available. Large graphs scroll instead of
shrinking node labels. Task groups support pointer, Enter, and Space selection
and expose accessible labels. Details show type, duration, dependencies, size,
rank, processor, start/end, and completed status. Types have distinct colors/text.

Changed inputs retain the old results with a notice and disable saving until a
rerun. Policy inspection does not discard other pending input edits. JSON equality
canonicalizes key order so backend serialization does not create false stale
states. User names use `textContent`, not HTML. Old history responses are
discarded after account identity changes. Playback is deferred.

## Append-only storage

The UTF-8 JSONL event log stores one JSON object plus newline per event:

```json
{"schema":1,"event":"experiment_renamed","at":"2026-10-06T18:00:00+00:00","data":{"id":"<experiment ID>","owner_id":"<user ID>","name":"Updated name"}}
```

Real IDs are UUID4 hexadecimal strings; the example uses placeholders.

| Event | Data |
| --- | --- |
| `user_created` | ID, username, unique lowercase key, password hash, creation time |
| `experiment_created` | ID, owner ID, name, canonical configuration, full DAG/results/comparisons, simulator version, creation time |
| `experiment_renamed` | Experiment ID, owner ID, new name |
| `experiment_deleted` | Experiment ID, owner ID |

Configuration includes form, parameters, processors, and policy. Full results
include every task, assignment, idle interval, and metric for all policies.
Temporary processor state is not stored.

A threading lock and cross-process `portalocker` lock on the adjacent `.lock`
file surround the **whole** read/validate/mutate/append transaction. Username
uniqueness and ownership checks happen within it. Appends write a complete
newline-delimited payload, flush, and `fsync` before returning. Normal operations
never rewrite earlier bytes. Replay applies updates/deletions in order. Deleted
experiments disappear from retrieval, but historical bytes remain in the log.

Replay validates schema, IDs, usernames/hashes, ownership, names, timestamps,
configuration, generated DAG/ranks, and deterministic results. Simulator version
1.0.0 is supported; changing the algorithm requires an explicit log migration
before incompatible records load. Reads are linear in historical log size and
verify small schedules; this is a course-scale design. Compaction/indexing are
future work, and deletion still consumes disk space.

A machine crash may interrupt an append despite locks/fsync. Malformed JSON,
unknown schema, or an incomplete final line fails closed: the API responds 503,
logs a diagnostic, and preserves the file. Recovery: stop the service, back up
the log, restore a known-good snapshot or remove only a verified incomplete
trailing record, then restart. Do not edit a live log. Silent automatic truncation
was avoided because it can hide data loss.

## Accounts and production

Usernames are case-insensitively unique, 3–30 ASCII letters/digits/underscores.
Passwords are 8–128 characters, hashed/verified with Werkzeug scrypt
(`32768:8:1`, random 16-character salt). A dummy hash is verified for missing
accounts. Passwords are never stored as plaintext or returned.

Flask's signed session stores the user ID, resolved through storage on private
routes. Body owner IDs are ignored. Every read, rename, and delete checks
ownership; unknown and unowned experiments both return 404. Guests receive 401.
All API mutations require a session-bound `X-CSRF-Token`. Registration, login,
and logout clear the old session and rotate the token.

Cookies are HttpOnly, SameSite=Lax, Secure in production, with a seven-day
lifetime. Production requires HTTPS, a stable secret of at least 32 characters,
and an absolute persistent storage path. ProxyFix trusts one Render proxy hop
for client IP/scheme; do not reuse it behind an untrusted forwarding topology.
Frontend/API share one origin; no permissive CORS policy is configured. A
restrictive CSP, anti-framing and MIME-sniffing headers, uncached API responses,
and a 32 KiB body limit are included.

Registration/login share limits of 20 attempts/IP and 10/username per 15 minutes.
Counters are bounded, thread-safe, in-memory, and reset on restart. Use the
configured one Gunicorn worker with four threads; multiple workers would need
a shared limiter backend. Password failure messages do not identify whether an
account exists.

Render uses `/var/data/records.jsonl` on a persistent disk. Gunicorn is the
production entry point; `python app.py` is local development. The Blueprint needs
provisioning in a Render account. Actual remote restart/redeployment persistence
has not yet been verified.
