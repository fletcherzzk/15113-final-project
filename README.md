# Parallel Scheduling Lab

A Flask application for exploring the work–span model with **Map** and
**Divide-and-Conquer** computations. Configure a computation, simulate it,
inspect an aligned processor timeline, and compare three scheduling heuristics.
Guests can run simulations; accounts can privately save, load, rename, and
delete experiments.

Implements the core of [the specification](Parallel_Scheduling_Lab_Spec.md).
Optional overhead, exact optimization, measured durations, size-dependent
costs, and playback are deferred.

## Run locally

Use Python 3.11 or later. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open **http://127.0.0.1:5000**. No frontend build step, database, or Node runtime
is required to run the application. Local records go to `storage/records.jsonl`,
which is excluded from Git. The app serves its frontend and API on one origin.

The implementation machine's Python executable and standard library were in
different locations. An ignored `.runtime/` copy and prepared `.venv/` were used
for verification there. A normal Python installation does not need `.runtime/`.

Set a stable `SECRET_KEY` to preserve login cookies across local server restarts:

```powershell
$env:SECRET_KEY = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.venv\Scripts\python.exe app.py
```

The development fallback creates a random key at startup, so old sessions expire
on restart while saved accounts and experiments remain on disk. `.env.example`
documents settings; the app does **not** automatically load `.env` files.

## Using the lab

1. Select Map or Divide & conquer and enter parameters. Map presets are included.
2. Select a processor count with `1 ≤ P < N`, where N counts computation tasks.
3. Run. All three policies are calculated for the same input.
4. Use **View** in the comparison table to inspect a policy's schedule. Select
   a timeline block or DAG node for details. The supporting DAG is collapsed initially.
5. Register or log in, name the experiment, and use **Save**. Running does
   not save automatically. Changed inputs require a new run before saving.
6. Saved experiments appear below the lab with load, rename, and delete actions.

The default `[3, 3, 2, 2, 2]` example on two processors finishes in **7** units
under all three heuristics. Its lower bound is **6**, attainable by putting the
two 3-unit tasks on one processor and the three 2-unit tasks on the other.
The app compares heuristics; it does not search for or claim an optimal schedule.

## Verify

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

Frontend integration tests additionally require Node 22.13+:

```sh
npm ci
npm test
```

These use JSDOM to execute the actual frontend JavaScript against an isolated
Flask process, with an independent cookie session per fixture. Test accounts and
logs live under ignored `artifacts/` directories. The server starts/stops
automatically; a separate running app is unnecessary. Set `PYTHON_EXECUTABLE`
if Python is outside `.venv/` and `PATH`.

Verification: **81 backend tests and 5 frontend integration tests passed**, plus
`node --check static/app.js`. JSDOM does not verify browser layout, native dialog
focus, or screenshot quality. No browser surface was available during
implementation, so browser visual QA remains manual. See
[the acceptance checklist](docs/VERIFICATION.md).

## Deploy on Render

[`render.yaml`](render.yaml) defines a Python web service, Gunicorn, secure
production settings, and a persistent disk mounted at `/var/data`. Deployment
has **not** been performed by this implementation.

1. Push this repository to your GitHub account.
2. In Render, create a **Blueprint** from the repository and review the service
   and disk before provisioning. The Blueprint selects a paid `starter` service
   because persistent disks require a paid service.
3. Keep the generated `SECRET_KEY` stable. `APP_ENV=production` and
   `STORAGE_PATH=/var/data/records.jsonl` are already defined in the Blueprint.
4. Verify `/api/health` on the HTTPS URL. Register, save, restart, and load an
   experiment to test persistence in your account.
5. Redeploy and repeat the load check.

Only files under Render's configured disk mount survive redeployment; the rest
of the filesystem is ephemeral. Keep **one Gunicorn worker with four threads**:
the authentication limiter shares counters inside one process. Back up the log
and retain the stable secret in Render's environment settings.

Official references: [Flask deployment](https://render.com/docs/deploy-flask),
[persistent disks](https://render.com/docs/disks), and
[Blueprint configuration](https://render.com/docs/blueprint-spec).

## Project guide

| Component | Responsibility |
| --- | --- |
| `lab/simulation.py` | Validation, DAG generation, ranks, scheduling, metrics |
| `lab/auth.py` | Credential constraints and authentication rate limiting |
| `lab/storage.py` | Locked append-only JSONL records, validation, replay, ownership |
| `app.py` | App factory, sessions, CSRF, API routes, security headers |
| `wsgi.py` | Gunicorn entry point |
| `templates/index.html` | Inputs, results, accounts, and history |
| `static/app.js` | Fetch integration and interactive SVG timelines/DAGs |
| `static/styles.css` | Responsive visual layout |
| `tests/` | Backend and frontend acceptance tests |

See [design and storage decisions](docs/DESIGN.md), [API documentation](docs/API.md),
and [AI assistance and study notes](docs/AI_ASSISTANCE.md).
