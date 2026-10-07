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
| Accounts/CSRF/production | Hash records, rotated signed header sessions/CSRF, rate limits, HTTPS enforcement |
| Split hosting/CORS | Separate static/API servers, actual OPTIONS exchanges, exact-origin rejection, no cookies |
| Session persistence and expiry | Reload retains login through sessionStorage; modified/expired signatures become anonymous |
| Pages artifact | Public assets only, relative paths, generated HTTPS API configuration/CSP, invalid URL rejection |
| Aligned primary timeline | Frontend test checks common SVG axis and identical row extents |
| Collapsible supporting DAG | Nodes/joins render; collapsing leaves the timeline present |
| UI history and validation | Register/save/load/rename/delete/login, stale state, invalid inputs |
| Map policy equivalence | Two options/rows with a combined label; saved `critical` Map loads cleanly; rerun uses `longest` |
| D&C policy separation | Three options/rows; critical remains independently selectable; unrun edits retain prior comparisons |
| Safe text/network errors | HTML-like names remain text; fetch failures release buttons |

Verification: **91 Python tests and 8 Node/JSDOM/frontend build tests passed**;
JavaScript syntax validation passed. CI is configured for Linux/Windows but remote
CI has not been triggered here.

## Manual browser review still needed

No browser surface was available. JSDOM tests behavior/coordinates but does not
render layout or native focus. In a browser:

1. Check larger text at desktop/mobile widths, horizontal scrolling, the combined
   Map label, shared timeline ticks, and enlarged DAG nodes. Check wrapped policy
   and preset values, two columns above 760px, and narrow/short-viewport dialogs.
2. Run maximum Map/D&C inputs with P=N−1. Inspect trailing idle time, arrows,
   split/base/combine labels, and processor rows.
3. Check keyboard task selection, native dialog focus/Escape, and form navigation.
4. Register, reload, logout/login, and verify a second account's private history.
5. Load, edit, rerun, compare policies, and save; verify the selected schedule is saved.

## GitHub Pages and Render verification still needed

The persistent-disk Blueprint is included; no Render service has been provisioned.
After deploying from your account:

1. Verify the Pages workflow and repository `API_BASE_URL`, Render HTTPS/health,
   exact `FRONTEND_ORIGINS`, stable secret, and `/var/data` disk mount.
2. Register, save, and rename an experiment.
3. Restart, log in, and load it; compare saved metrics/timeline/configuration.
4. Redeploy and repeat the load check.
5. Delete, restart, and ensure the experiment does not reappear.
6. Reload the Pages site while signed in. Verify Authorization and CSRF headers,
   successful preflights, and exposed X-Session-Token. Test with third-party cookies
   disabled; no Set-Cookie or credentialed cookie requests should occur.
7. Verify `<Render URL>/` and `/static/app.js` return 404 and only the public
   frontend build assets appear in the Pages artifact.

Local restart tests prove replay from the same file, but cannot prove the hosting
account attached/retained its persistent disk correctly.
