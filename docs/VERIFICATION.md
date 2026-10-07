# Acceptance verification

| Requirement | Evidence |
| --- | --- |
| Every task executes once | Assignment uniqueness/count assertions across generated graphs |
| Dependencies/durations/no overlap | Predecessor timing, duration, and per-processor interval assertions |
| Single processor T=W; T≥lower bound | Schedule invariants over every supported D&C shape |
| Uniform map formula | N=2,5,8,16; durations=1,3,20; every valid P and policy |
| Nonuniform example | Exact makespan-7 timeline and manual makespan-6 partition |
| D&C children/joins | All n/k/b combinations; child sizes, join edges, start timing |
| Policies/ties/determinism | Distinct rank/duration cases, numeric ID and processor order, repeated schedules |
| Simultaneous completion events | Join starts after both completions are processed together |
| Validation and task cap | Invalid form/type/range tests and maximum 22-task graph |
| Private experiments | Another user cannot list/read/rename/delete the owner's records |
| Append/replay/persistence | Earlier bytes retained; new app instance restores stored results |
| Concurrent storage | Distinct store instances append concurrently; registration stays unique |
| Corruption | Truncated/invalid records and modified schedules fail closed without overwrites |
| Accounts/CSRF/production | Hash records, rotated tokens, rate limits, secure cookies, HTTPS enforcement |
| Aligned primary timeline | Frontend test checks common SVG axis and identical row extents |
| Collapsible supporting DAG | Nodes/joins render; collapsing leaves the timeline present |
| UI history and validation | Register/save/load/rename/delete/login, stale state, invalid inputs |
| Safe text/network errors | HTML-like names remain text; fetch failures release buttons |

Verification: **81 Python tests and 5 Node/JSDOM integration tests passed**;
JavaScript syntax validation passed. CI is configured for Linux/Windows but remote
CI has not been triggered here.

## Manual browser review still needed

No browser surface was available. JSDOM tests behavior/coordinates but does not
render layout or native focus. In a browser:

1. Check desktop/mobile widths, horizontal scrolling, labels, shared timeline ticks.
2. Run maximum Map/D&C inputs with P=N−1. Inspect trailing idle time, arrows,
   split/base/combine labels, and processor rows.
3. Check keyboard task selection, native dialog focus/Escape, and form navigation.
4. Register, reload, logout/login, and verify a second account's private history.
5. Load, edit, rerun, compare policies, and save; verify the selected schedule is saved.

## Render verification still needed

The persistent-disk Blueprint is included; no Render service has been provisioned.
After deploying from your account:

1. Verify HTTPS, health, Secure cookies, stable secret, and `/var/data` disk mount.
2. Register, save, and rename an experiment.
3. Restart, log in, and load it; compare saved metrics/timeline/configuration.
4. Redeploy and repeat the load check.
5. Delete, restart, and ensure the experiment does not reappear.

Local restart tests prove replay from the same file, but cannot prove the hosting
account attached/retained its persistent disk correctly.
