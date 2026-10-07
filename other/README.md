# Parallel Scheduling Lab

A static frontend and Flask API for exploring the work–span model with **Map** and
**Divide-and-Conquer** computations. Configure a computation, simulate it,
inspect an aligned processor timeline, and compare scheduling heuristics. Map
shows **Fixed order** and **Longest Task First / Critical Path First** as two
options because longest task and critical path priorities are equivalent for
independent tasks. Divide-and-Conquer keeps all three policies separate.
Guests can run simulations; accounts can privately save, load, rename, and
delete experiments.

Implements the core of [the specification](Parallel_Scheduling_Lab_Spec.md).
Optional overhead, exact optimization, measured durations, size-dependent
costs, and playback are deferred.

## Run locally

Use Python 3.11 or later. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.venv\Scripts\python.exe backend/app.py
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/app.py
```

No frontend build step, database, or Node runtime
is required to run the application locally. Flask is **API-only** on port 5000;
it does not serve HTML, CSS, JavaScript, or the frontend homepage. Local records
go to `backend/storage/records.jsonl`, which is excluded from Git.

Start the static frontend in a **second terminal**, from the repository root:

```powershell
.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory frontend
```

On macOS/Linux use `.venv/bin/python` for the same command. Open
**http://127.0.0.1:8000**. `frontend/config.js` points localhost development to
`http://127.0.0.1:5000`; Flask allows frontend origins on port 8000 by default.
Use an HTTP server instead of opening `index.html` as a file. If you change ports,
update the API URL in `config.js` and set `FRONTEND_ORIGINS` on the backend.

The implementation machine's Python executable and standard library were in
different locations. An ignored `.runtime/` copy and prepared `.venv/` were used
for verification there. A normal Python installation does not need `.runtime/`.

Set a stable `SECRET_KEY` to preserve signed login sessions across backend restarts:

```powershell
$env:SECRET_KEY = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.venv\Scripts\python.exe backend/app.py
```

The development fallback creates a random key at startup, so old sessions expire
on restart while saved accounts and experiments remain on disk. `backend/.env.example`
documents settings; the app does **not** automatically load `.env` files.

## Using the lab

1. Select Map or Divide & conquer and enter parameters. Map presets are included.
2. Select a processor count with `1 ≤ P < N`, where N counts computation tasks.
3. Run. Compare two policy options for Map or three policies for Divide & conquer.
4. Use **View** in the comparison table to inspect a policy's schedule. Select
   a timeline block or DAG node for details. The supporting DAG is collapsed initially.
5. Register or log in, name the experiment, and use **Save**. Running does
   not save automatically. Changed inputs require a new run before saving.
6. Saved experiments appear below the lab with load, rename, and delete actions.

The default `[3, 3, 2, 2, 2]` example on two processors finishes in **7** units
under both displayed Map options. Its lower bound is **6**, attainable by putting the
two 3-unit tasks on one processor and the three 2-unit tasks on the other.
The app compares heuristics; it does not search for or claim an optimal schedule.

## Verify

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.venv\Scripts\python.exe -m pytest -c backend/pytest.ini -q
```

Frontend integration tests additionally require Node 22.13+:

```sh
npm --prefix frontend ci
npm --prefix frontend test
```

These use JSDOM to execute the actual frontend JavaScript against independent
static and Flask servers. They exercise a GitHub Pages-style repository subpath,
actual CORS preflights, and signed header sessions with all cookies omitted. Test accounts and
logs live under ignored `other/artifacts/` directories. The server starts/stops
automatically; a separate running app is unnecessary. Set `PYTHON_EXECUTABLE`
if Python is outside `.venv/` and `PATH`.

Verification: **91 backend tests and 7 frontend/build tests passed**, plus
`node --check frontend/static/app.js`. JSDOM does not verify browser layout, native dialog
focus, or screenshot quality. No browser surface was available during
implementation, so browser visual QA remains manual. See
[the acceptance checklist](docs/VERIFICATION.md).

## Deploy the backend on Render

[`render.yaml`](render.yaml) defines an API-only Python service rooted in `backend/`, Gunicorn, secure
production settings, and a persistent disk mounted at `/var/data`. Deployment
has **not** been performed by this implementation.

1. Push this repository to your GitHub account.
2. In Render, create a **Blueprint** from the repository using `other/render.yaml`
   as its Blueprint path and review the service
   and disk before provisioning. The Blueprint selects a paid `starter` service
   because persistent disks require a paid service.
3. Keep the generated `SECRET_KEY` stable. `APP_ENV=production` and
   `STORAGE_PATH=/var/data/records.jsonl` are already defined. Set `FRONTEND_ORIGINS`
   to your Pages **origin**: `https://fletcherzzk.github.io` for this repository.
   Do not include `/15113-final-project/` or a trailing slash. If you fork the repo
   or use a custom domain, change this value. Multiple exact origins can be comma-separated.
4. Copy the actual Render HTTPS URL, such as `https://your-service.onrender.com`.
   Check `<Render URL>/api/health`. The backend's `/` and `/static/...` return 404
   because it only provides API routes.
5. Deploy the frontend below, then register/save/load an experiment through Pages.
   Restart and redeploy the backend and verify that saved experiments persist.

Only files under Render's configured disk mount survive redeployment; the rest
of the filesystem is ephemeral. Keep **one Gunicorn worker with four threads**:
the authentication limiter shares counters inside one process. Back up the log
and retain the stable secret in Render's environment settings.

Official references: [Flask deployment](https://render.com/docs/deploy-flask),
[persistent disks](https://render.com/docs/disks), and
[Blueprint configuration](https://render.com/docs/blueprint-spec).

## Deploy the frontend on GitHub Pages

All frontend source and build code are in `frontend/`. The workflow
[`pages.yml`](../.github/workflows/pages.yml) publishes only `index.html`,
`config.js`, `.nojekyll`, and the static CSS/JS. Backend files, tests,
`node_modules`, account records, and secrets are never part of the Pages artifact.

1. Push the changes to this repository's `main` branch.
2. In GitHub **Settings → Pages**, select **GitHub Actions** as the publishing source.
3. In **Settings → Secrets and variables → Actions → Variables**, add the repository
   variable `API_BASE_URL` with the actual Render HTTPS **origin**, e.g.
   `https://your-service.onrender.com`. Do not append `/api`. This public URL is
   configuration, not a secret. Never place `SECRET_KEY` in the frontend or this variable.
4. Run **Deploy frontend to GitHub Pages** in Actions. Subsequent frontend changes
   pushed to `main` also deploy. If you change the variable without changing files,
   rerun the workflow manually.
5. Open the deployment URL. For this repository it is expected to be
   `https://fletcherzzk.github.io/15113-final-project/`. Relative asset/home URLs
   work under that repository subpath and with a custom domain.
6. Verify login, reload, policy comparison, save/load/rename/delete, and logout.

The build requires `API_BASE_URL`, writes the Render address into `config.js`, and
restricts the frontend CSP's `connect-src` to that API origin. It fails before
publishing if the URL is missing, not HTTPS, or contains a path/credentials.
No bundler or `npm install` is needed for the deployment build. To inspect it locally:

```powershell
$env:API_BASE_URL = 'https://your-service.onrender.com'
npm --prefix frontend run build
```

Output is `other/artifacts/pages/`. GitHub's branch-based Pages source cannot
publish `frontend/` directly; use the included Actions workflow. Official guide:
[custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

The deployment workflows/configuration are prepared, but live deployment has not
been performed in this session. It needs your Render service URL, GitHub settings,
and account access. Render and GitHub integrations can provide that access if installed/connected.

## Cross-origin login and troubleshooting

The frontend fetches `${API_BASE_URL}/api/...` with `credentials: "omit"` and sends
the signed API session as `Authorization: Bearer <token>`. Flask returns updated
sessions through `X-Session-Token`. The frontend stores them in **sessionStorage**
under a key specific to the API origin. Login survives reloads in the same tab;
closing that tab ends its locally stored session. Passwords are never stored there.
If browser storage is disabled, login works in memory until reload.

This avoids relying on third-party cookies between `github.io` and `onrender.com`.
Flask still maintains session identity, rotates CSRF tokens on account operations,
checks ownership, and expires signed tokens after seven days without renewal.
Tokens are bearer credentials: frontend scripts can access them, so the static
site uses restrictive CSP and text-only rendering for user names. No cross-site
cookies or `Access-Control-Allow-Credentials` are needed.

CORS allows only exact `FRONTEND_ORIGINS`, supports OPTIONS requests for the real
route methods, permits Authorization/Content-Type/X-CSRF-Token, and exposes
X-Session-Token/Retry-After. Unknown origins are rejected before mutations.
If the browser reports CORS errors, compare its **Origin** header to
`FRONTEND_ORIGINS` (scheme, hostname, and port must match). Verify the generated
`config.js`, API HTTPS URL, and preflight response in browser developer tools.
An expired session's CSRF error asks for a refresh; the session endpoint restores
anonymous access and the user can log in again.

Existing user and experiment files remain compatible. The old cookie-based
session requires one new login after this change; saved data is preserved.

## Project guide

All application files are grouped into three folders. Commands above run from
the repository root (the parent of these folders).

```text
frontend/                HTML, CSS, JavaScript, and frontend tests
  index.html
  config.js
  .nojekyll
  static/
  scripts/               Pages artifact builder
  tests/
  package.json
  package-lock.json
backend/                 Flask, simulation, persistence, and backend tests
  app.py
  wsgi.py
  lab/
  tests/
  requirements.txt
  requirements-dev.txt
  pytest.ini
  .env.example
  storage/               ignored local account/experiment data
other/                   Specification, documentation, deployment, test artifacts
  README.md
  Parallel_Scheduling_Lab_Spec.md
  docs/
  render.yaml
  artifacts/             ignored test outputs
```

Git configuration and `.github/workflows/` remain at the repository root, where
Git and GitHub require them. The ignored local Python environment/runtime also
remain there. Frontend Node dependencies are under `frontend/node_modules/`.

| Component | Responsibility |
| --- | --- |
| `backend/lab/simulation.py` | Validation, DAG generation, ranks, scheduling, metrics |
| `backend/lab/auth.py` | Credential constraints and authentication rate limiting |
| `backend/lab/storage.py` | Locked append-only JSONL records, validation, replay, ownership |
| `backend/app.py` | App factory, sessions, CSRF, API routes, security headers |
| `backend/wsgi.py` | Gunicorn entry point |
| `frontend/index.html` | Standalone static inputs, results, accounts, and history |
| `frontend/config.js` | API origin (local default; generated for Pages) |
| `frontend/scripts/build-pages.cjs` | Public Pages artifact and production CSP |
| `frontend/static/app.js` | Fetch integration and interactive SVG timelines/DAGs |
| `frontend/static/styles.css` | Responsive visual layout |
| `backend/lab/sessions.py` | Signed Flask sessions transported through API headers |
| `backend/tests/`, `frontend/tests/` | Backend and frontend acceptance tests |

See [design and storage decisions](docs/DESIGN.md), [API documentation](docs/API.md),
and [AI assistance and study notes](docs/AI_ASSISTANCE.md).
