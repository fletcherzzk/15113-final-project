# Parallel Scheduling Lab


## AI-generated documentation

### What the project does

Parallel Scheduling Lab is a web app for exploring how task dependencies,
processor counts, and scheduling rules affect parallel performance. It connects
the work-span model from 15-210 to schedules you can inspect visually.

The app supports **Map**, with independent tasks of configurable durations, and
**Divide-and-Conquer**, with recursive split, base-case, and combine tasks.
The Flask backend generates a dependency graph and simulates scheduling policies.
The HTML/CSS/JavaScript frontend shows work, span, completion time, speedup,
utilization, and a theoretical lower bound, alongside processor timelines and
an interactive dependency graph.

Guests can run simulations. Registered users can privately save, load, rename,
and delete experiments. The model assumes identical processors, fixed durations,
and no preemption or scheduling overhead. It compares heuristics rather than
searching for an optimal schedule. See the [specification](Parallel_Scheduling_Lab_Spec.md).

### How to use it

1. Open the frontend after starting the local servers described below.
2. Select **Map** or **Divide & conquer**. For Map, enter task durations or choose
   a preset. For Divide-and-Conquer, set the problem size, split ratio, base-case
   threshold, and split/base/combine costs.
3. Choose a processor count with `1 <= P < N`, where `N` is the number of
   computation tasks, and select a scheduling policy.
4. Click **Run simulation** to compare policies on the same inputs. Map displays
   Fixed order and Longest Task First / Critical Path First because the latter
   priorities are equivalent for independent tasks. Divide-and-Conquer compares
   all three policies separately.
5. Use **View** in the comparison table to inspect a schedule. Select a timeline
   block for task details, or expand **Computation dependencies** and select a node.
6. Register or log in, name an experiment, and click **Save** to keep it.
   Saved results appear under **Your experiments**, with load, rename, and delete
   actions. Saving is explicit; changed inputs require another run before saving.

For example, Map durations `3, 3, 2, 2, 2` on two processors finish in 7 time units
under both displayed policies, although the lower bound is 6. This illustrates
why a heuristic's result can differ from a theoretical lower bound.

### Features to consider for your personal reflection

These implemented highlights can help you choose what to discuss. Rewrite the
ones you are most proud of using your own reasons and experience:

- **Policy comparison:** each run compares scheduling choices on identical inputs,
  making changes in completion time easy to see.
- **Interactive visualizations:** processor timelines show assignments and idle
  time, while the dependency graph explains why tasks must wait for others.
- **Recursive modeling:** Divide-and-Conquer includes both branching and joining
  dependencies, so combine tasks wait for their child computations.
- **Private experiment history:** persistent storage and account ownership checks
  let users keep their own experiments and revisit them later.

// this is direct use and experiment for me to better learn 15210
// I am proud of my decisions for implementation details

### Run locally

Install Python 3.11 or later. Run these commands from the repository root.
Use two terminals: one for the API and one for the frontend. No Node runtime,
frontend build, or separate database is needed for local use.

On Windows, start the backend:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.venv\Scripts\python.exe backend/app.py
```

In a second terminal, start the frontend:

```powershell
.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory frontend
```

On macOS/Linux, start the backend:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/app.py
```

In a second terminal:

```sh
.venv/bin/python -m http.server 8000 --bind 127.0.0.1 --directory frontend
```

Open **http://127.0.0.1:8000**. Flask runs on port 5000 and serves only the API.
Use the HTTP server instead of opening `index.html` directly.
`frontend/config.js` selects `http://127.0.0.1:5000` for local development.
If you change ports, update that configuration and set `FRONTEND_ORIGINS` on the
backend to the frontend's exact origin.

Accounts and experiments are stored in `backend/storage/records.jsonl`, which
is ignored by Git.

### How secrets and account data are handled

`SECRET_KEY` is the backend secret used to sign sessions. Set it through your
shell or hosting provider's environment settings. Keep it out of committed files
and frontend code. For example, before starting the backend on Windows:

```powershell
$env:SECRET_KEY = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.venv\Scripts\python.exe backend/app.py
```

Without this setting, local development generates a random key at startup.
Existing sessions then expire on restart, while saved accounts and experiments
remain. Reuse a stable secret if sessions should survive restarts. Production
requires a key of at least 32 characters and an absolute `STORAGE_PATH` pointing
to persistent storage.

[`backend/.env.example`](backend/.env.example) documents settings without real
secrets. The app does **not** automatically load `.env` files.
`FRONTEND_ORIGINS` and the public API URL are configuration, not secrets.

Passwords are stored as Werkzeug password hashes rather than plaintext.
The frontend keeps signed bearer session tokens in `sessionStorage` for the
current tab, or in memory if browser storage is unavailable. Tokens are sensitive
credentials; passwords are not stored in browser storage. Closing the tab clears
its stored session. Keep account records private and out of Git and the public
frontend deployment.

### AI use and citations

The [prompt log](promptlog.md) records use of ChatGPT/Codex with the 6.1 Sol model
in the IDE. The student worked with AI on the specification and provided the
strategy, design, and benchmarks. According to the existing
[AI assistance notes](other/docs/AI_ASSISTANCE.md), Codex generated substantial
portions of the implementation, tests, deployment configuration, and documentation.
This included scheduling logic, frontend/API integration, accounts and storage,
the Pages build, CORS handling, and signed header sessions. Codex also drafted
this README revision. The student should add their own account of what they
reviewed, verified, and learned.

The AI assistance notes identify official Render, GitHub, Flask, and MDN
documentation as development references. Relevant deployment references recorded
in the previous README include
[Render's Flask deployment guide](https://render.com/docs/deploy-flask),
[Render persistent disks](https://render.com/docs/disks),
[Render Blueprint configuration](https://render.com/docs/blueprint-spec), and
[GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
The repository does not identify a specific adapted outside code excerpt.

### Project files and verification

- `frontend/`: static interface, API configuration, Pages builder, and tests.
- `backend/`: Flask API, simulation logic, authentication, storage, and tests.
- `other/`: supporting documentation, Render configuration, and ignored artifacts.
- `.github/workflows/`: GitHub Actions workflows.

Run backend tests on Windows:

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.venv\Scripts\python.exe -m pytest -c backend/pytest.ini -q
```

On macOS/Linux, use `.venv/bin/python` in those commands.
Frontend/build tests require Node 22.13 or later:

```sh
npm --prefix frontend ci
npm --prefix frontend test
```

Further details: [design notes](other/docs/DESIGN.md),
[API documentation](other/docs/API.md),
[verification checklist](other/docs/VERIFICATION.md),
[Render configuration](other/render.yaml), and
[Pages workflow](.github/workflows/pages.yml).

This file is written by AI. 
