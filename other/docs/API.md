# API

Flask is API-only on Render; the static frontend lives on GitHub Pages. Responses are JSON; errors have
`{"error":"Human-readable message"}`. Bodies must be JSON objects and ≤32 KiB.

Start with `GET <API_BASE_URL>/api/session` to establish a signed header session.
The JSON body is `{"user":null,"csrf_token":"<token>"}` and the response's
`X-Session-Token` header contains the signed session. Send that value as
`Authorization: Bearer <session-token>` on subsequent requests and retain the
updated `X-Session-Token` response header. Send `X-CSRF-Token` for **every**
POST/PATCH/DELETE. Login/register/logout rotate CSRF and signed session values.
API responses use `Cache-Control: no-store`; no cookies are read or written.

Browser requests must originate from an exact `FRONTEND_ORIGINS` entry. Successful
preflight responses allow Authorization, Content-Type, and X-CSRF-Token and expose
X-Session-Token/Retry-After. Fetch uses `credentials: "omit"`. Unknown origins receive
403 without allowed-origin/session headers. CLI clients may omit Origin, but need
the same session and CSRF credentials. API route paths below are relative to the
configured Render origin; `/` and `/static/...` return JSON 404.

Example browser bootstrap:

```js
const response = await fetch(`${apiBaseUrl}/api/session`, { credentials: "omit" });
const sessionToken = response.headers.get("X-Session-Token");
const { csrf_token } = await response.json();
await fetch(`${apiBaseUrl}/api/simulate`, {
  method: "POST",
  credentials: "omit",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${sessionToken}`,
    "X-CSRF-Token": csrf_token,
  },
  body: JSON.stringify(configuration),
});
```

## Accounts

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{"status":"ok"}` |
| GET | `/api/session` | — | Public user (or null) and CSRF token |
| POST | `/api/register` | `{"username":"alice","password":"example-password"}` | 201, public user/new token; signs in |
| POST | `/api/login` | Same credential shape | Public user/new token |
| POST | `/api/logout` | `{}` | Null user/new token |

Public users expose only ID/username. Attempts may return 429 with
`Retry-After: 900`. Passwords are never returned.

## Simulation

`POST /api/simulate` works for guests. Map request:

```json
{"form":"map","parameters":{"durations":[3,3,2,2,2]},"processors":2,"policy":"longest"}
```

D&C request:

```json
{
  "form":"dc",
  "parameters":{"n":8,"k":3,"b":1,"split_duration":1,"base_duration":3,"combine_duration":2},
  "processors":3,
  "policy":"critical"
}
```

Policies are `fixed`, `longest`, and `critical`. Limits appear in the design notes.
Normalization includes only supported fields; extra fields cannot supply edges,
overhead, or ownership. Responses contain:

| Field | Contents |
| --- | --- |
| `configuration` | Canonical form, parameters, processor count, policy |
| `simulator_version` | `1.0.0` |
| `dag` | Task `id`, `type`, `duration`, `dependencies`, `size`, `depth`, `rank` |
| `results` | Selected policy result |
| `comparisons` | Results keyed by all three policies |

Each result has `policy`, `timeline`, `idle_intervals`, and `metrics`. Timeline
entries contain `task_id`, `processor_id`, `start`, `end`; IDs start at 1. Idle
entries contain `processor_id`, `start`, `end`. Metrics are `work`, `span`,
`average_parallelism`, `makespan`, `speedup`, `utilization` (fraction), and
`lower_bound`. Time/duration values are simulated units.

## Private experiments

All experiment routes require login. Identity comes from the session.

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| GET | `/api/experiments` | — | `{"experiments":[...]}` summaries, newest first |
| POST | `/api/experiments` | `{"name":"Example","configuration":{...}}` | 201, full saved record |
| GET | `/api/experiments/<id>` | — | Stored record with configuration/results |
| PATCH | `/api/experiments/<id>` | `{"name":"Renamed"}` | Updated record |
| DELETE | `/api/experiments/<id>` | — | `{"deleted":true}` |

Names are trimmed, 1–80 characters, without control characters. Summaries expose
ID, name, configuration, simulator version, and creation time. Full records add
owner ID and `experiment` containing the DAG/results. Saving recomputes schedules;
submitted results/owner IDs are ignored. Running and saving are separate.

Status codes: 400 invalid input/JSON, 401 login required/failed, 403 CSRF failure,
404 missing/unowned experiment, 409 username conflict, 413 oversized request,
422 structural graph error, 429 account rate limit, 503 unavailable/corrupt
storage. HTTPS is mandatory in production except for the health transport check.
