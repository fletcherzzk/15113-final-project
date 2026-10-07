# Parallel Scheduling Lab Specification

Version: 1.2 — Planning specification  
Date: October 6, 2026

## 1. Purpose and Scope

Parallel Scheduling Lab is a web application for exploring how computation structure, processor count, and scheduling rules affect parallel performance. It connects the work–span model studied in 15-210 with interactive scheduling experiments.

**The application shall accept exactly two input forms: Map or Divide-and-Conquer (D&C).** Unrestricted user-defined DAGs are outside the core scope. The backend shall generate a computation DAG from the selected input form and its parameters.

Users shall be able to run simulations, inspect results, compare scheduling policies, and save experiments under their accounts. Core functionality includes frontend–backend communication, file-based storage, and interactive visualization.

The TA has confirmed that AI may write all code. The student shall understand the important implementation details, verify behavior, and document design decisions and AI-assisted development.

## 2. Input Form A — Map

Each map task represents an independent computation on one element. The computation finishes when all tasks finish; the core model assigns no additional cost to the final join.

Requirements:

- Maximum task count: 16.
- Each task duration: an integer from 1 to 20 simulated time units.
- Users may specify different durations for different tasks.
- Preset examples shall support quick experimentation.
- Proposed minimum task count: 2, because the processor constraint requires at least one processor and strictly fewer processors than tasks.

Example input: [3, 3, 2, 2, 2].

Equal durations represent uniform map; different durations represent nonuniform map.

## 3. Input Form B — Divide-and-Conquer

Each non-base-case recursive call shall contain:

1. A sequential split task.
2. Two child computations that may execute in parallel.
3. A combine task that starts only after both child computations finish.

A base-case call shall contain one sequential task. The DAG shall include both downward branching and upward joining dependencies.

### 3.1 Parameters

| Parameter | Meaning |
|---|---|
| n | Initial problem size |
| k | Split ratio parameter, an integer at least 2 |
| b | Positive integer base-case threshold |
| Split duration | Cost of each split task |
| Combine duration | Cost of each combine task |
| Base-case duration | Cost of each leaf task |

A call is a base case when its size m is at most b. The initial implementation shall use fixed positive integer durations for the three task types. Size-dependent costs are an optional extension.

### 3.2 Split Rule

Every recursive split shall use the ratio 1/k : (k−1)/k. The same k shall apply throughout one experiment.

Rounding shall favor a more balanced allocation. For a non-base-case size m:

small = min(ceil(m/k), floor(m/2))  
large = m − small

This gives the smaller child the upward rounding adjustment without making it larger than half the parent.

| Parent size m | k | Child sizes |
|---:|---:|---|
| 10 | 3 | 4 and 6 |
| 8 | 3 | 3 and 5 |
| 5 | 2 | 2 and 3 |
| 3 | 4 | 1 and 2 |

Both child sizes shall be positive, sum to m, and be strictly smaller than m. With b at least 1, recursive splitting therefore terminates.

k = 2 produces the most balanced split available for the integer size. Larger k values produce more unequal splits, subject to rounding at small sizes.

### 3.3 D&C Input Limits and Validation

The application shall enforce the following limits for Divide-and-Conquer inputs:

- **Initial problem size (n):** an integer from 2 to 8.
- **Split parameter (k):** an integer from 2 to 8.
- **Base-case threshold (b):** an integer satisfying 1 ≤ b < n.
- **Split, base-case, and combine durations:** three independently configurable integers from 1 to 20 simulated time units. All tasks of the same type shall use the corresponding duration.
- **Processor count (P):** an integer satisfying 1 ≤ P < N, where N is the total number of generated split, base-case, and combine tasks.
- **Generated task limit:** at most 22 computation tasks. Display-only markers shall not count toward this limit.

The maximum task count occurs when n = 8 and b = 1, producing 8 base-case tasks, 7 split tasks, and 7 combine tasks.

The frontend shall display the valid input ranges and provide clear validation messages. The backend shall independently validate all parameters and enforce the generated task limit.

These limits apply specifically to D&C inputs. Map inputs shall retain their maximum of 16 tasks.

## 4. Processor Count

The user shall select an integer processor count P satisfying:

1 ≤ P < N

N shall mean the number of actual computation tasks in the generated DAG:

- Map: the number of map tasks.
- D&C: the total number of split, base-case, and combine tasks.

Display-only markers shall not count toward N. Inputs producing fewer than two computation tasks shall be rejected under this processor constraint.

The frontend shall show the valid range. The backend shall independently validate it.

## 5. Core Simulation Model

The core model shall assume:

- Identical processors.
- One processor per task.
- Nonpreemptive execution: a running task continues until completion.
- All predecessor tasks must finish before a task starts.
- Known, fixed task durations.
- No communication overhead.
- No scheduling or task-launch overhead in the core version.

Durations are simulation inputs, not measurements of user code. Simulated time units do not require real waiting, threads, or actual parallel execution.

## 6. Discrete Event Simulator

The backend shall implement a discrete event simulator.

Each task shall have an ID, type, duration, dependency information, and execution status. Each processor shall track its current task and finish time. The simulator shall record task assignments and start/end times.

At each event time, the simulator shall:

1. Mark all tasks finishing at that time as completed.
2. Release their processors.
3. Identify unstarted tasks whose predecessors have all completed.
4. Order those ready tasks using the selected policy.
5. Assign tasks to available processors.
6. Record the assignments.
7. Advance directly to the next completion time.

Simultaneous completions shall be processed together before selecting new tasks. If unfinished tasks remain but there are no running or ready tasks, the backend shall report a structural error.

Each timeline entry shall include task ID, processor ID, start time, and end time.

## 7. Scheduling Policies

The core application shall support all three policies:

| Policy | Priority among ready tasks |
|---|---|
| Fixed order | Earlier task ID first |
| Longest task first | Larger task duration first |
| Critical path first | Larger remaining critical-path duration first |

For critical-path priority:

rank(v) = duration(v) + max(rank(u) for direct successors u)

A task without successors has rank equal to its duration. Ranks may be computed in reverse topological order.

Ties shall be resolved by task ID. Available processors shall be selected by processor ID. Task IDs shall be generated deterministically.

These are heuristic policies and shall not be described as universally optimal. For independent map tasks, critical-path priority and longest-task priority are equivalent. A comparison may identify the fastest policy for the current experiment, without claiming global optimality.

## 8. Results and Visualization

The application shall display:

- The generated computation DAG as a collapsible supporting view of task dependencies.
- A processor timeline as the primary result visualization, with one row per processor.
- Task execution intervals and idle intervals.
- Work, span, completion time, speedup, and utilization.
- A comparison of policy results for identical inputs and processor counts.

All processor rows shall share the same aligned time axis so that concurrent execution and idle intervals can be compared directly. Collapsing the supporting DAG view shall leave the primary processor timeline available.

Selecting a task shall reveal its type, duration, dependencies, processor assignment, and start/end times. D&C task types shall be distinguishable.

Step-by-step playback of ready, running, completed, and dependency-blocked tasks is an interface enhancement to implement after static results are correct.

### 8.1 Core Metrics

| Metric | Definition |
|---|---|
| Work W | Sum of all computation-task durations |
| Span S | Duration of the longest dependency path |
| Average parallelism | W/S |
| Makespan T_P | Completion time with P processors |
| Speedup | W/T_P, because T_1 = W in the core model |
| Utilization | W/(P × T_P) |
| Time lower bound | max(W/P, S) |

The lower bound shall not be labeled as an optimal makespan unless attainability is separately established.

## 9. User Accounts and Experiment Storage

The core application shall support registration, login, logout, and private experiment storage.

Proposed guest behavior: guests may run simulations, but saving requires login.

Users shall be able to save, list, load, rename, and delete their experiments. Loading shall restore the saved configuration and results. Running and saving shall be separate operations.

### 9.1 File-Based Storage and Record Model

| Record type | Fields |
|---|---|
| users | User ID, unique username, password hash, creation time |
| experiments | Experiment ID, owner ID, name, input form, parameters, processor count, policy, results, simulator version, creation time |

Following the TA's recommendation, the application shall use file-based storage instead of a database. The Flask backend hosted on Render shall append new records to a storage file and read the accumulated records when retrieving saved data. Parameters, DAGs, and timeline results shall be serialized as JSON in the file.

Renames and deletions shall be recorded as appended updates or deletion markers. Retrieval shall apply these records in order to reconstruct the current saved data, excluding deleted experiments. File reads and appends shall be coordinated to prevent partial records or conflicting writes.

Temporary processor state shall exist only during simulation; it does not require persistent storage.

### 9.2 Account Requirements

- Store password hashes, never plaintext passwords.
- Use established password-hashing and verification libraries.
- Maintain login identity through a session.
- Derive the user identity from the authenticated session.
- Verify ownership for every experiment read, update, or deletion.
- Validate stored records and handle file reads and appends through the backend persistence component.
- Include appropriate HTTPS, cookie configuration, CSRF protection, and login rate limiting for deployment.
- Keep application secrets in environment variables.

Email verification, password recovery, and third-party login are outside the initial scope.

The Flask backend shall be hosted on Render. The storage file shall reside on persistent storage so user and experiment data survive application restarts and redeployment. The persistent storage arrangement and file format details remain to be finalized.

## 10. Technology and Architecture

The stack shall be:

- Backend: Python and Flask.
- Frontend: HTML, CSS, and JavaScript.
- Storage: file-based storage, following the TA's recommendation.
- Hosting: Render for the Flask backend.

Recommended deployment: Flask serves both the frontend files and API under one origin.

The implementation shall separate DAG generation, scheduling simulation, API handling, authentication, and persistence into understandable components.

| Frontend responsibilities | Backend responsibilities |
|---|---|
| Parameter input and immediate feedback | Authoritative validation |
| Submit requests using fetch | Generate Map or D&C DAGs |
| Render DAGs and timelines | Run scheduling simulation |
| Display metrics and comparisons | Compute metrics and return JSON |
| Registration and login interface | Verify passwords and maintain sessions |
| Experiment history interface | Persist records and enforce ownership |

## 11. Acceptance Criteria

The implementation shall verify that:

- Every task executes exactly once.
- Every task starts after all predecessors finish.
- Tasks assigned to the same processor do not overlap.
- Each execution interval equals the task duration.
- Single-processor completion time equals W in the core model.
- Completion time respects max(W/P, S).
- Uniform map completion time equals ceil(N/P) × task duration.
- D&C combine tasks wait for both child computations.
- Policy selections and tie-breaking follow the specified rules.
- Identical configurations produce identical results.
- Invalid inputs and excessive graph sizes are rejected.
- Users cannot access or modify other users' experiments.
- All processor rows use the same aligned time axis.
- The processor timeline is the primary result visualization, and the supporting DAG view can be collapsed.
- New storage records are appended to a file, and retrieval reads accumulated records to restore current saved data.
- Saved records persist across server restarts and redeployment.

Tests shall include small manually checked cases and a nonuniform map example with durations [3, 3, 2, 2, 2] on two processors. Longest-task and critical-path policies produce makespan 7, while an optimal arrangement has makespan 6.

## 12. Implementation Plan and Documentation

Recommended order:

1. Finalize persistent file storage/deployment details.
2. Implement and verify DAG generation and the simulator.
3. Connect the simulation API.
4. Build inputs, the primary processor timeline with a shared time axis, the collapsible supporting DAG view, and metrics.
5. Add authentication, persistence, and experiment history.
6. Deploy, verify, and complete documentation.
7. Implement optional add-ons only after core acceptance criteria pass.

Documentation shall explain model assumptions, algorithms, component responsibilities, verification, deployment, AI usage, and lessons learned.

The assignment's approximately eight-hour estimate is a reference budget. The current core scope may require roughly 10–16 hours of student wall-clock work, including understanding, debugging, deployment, and documentation. This is a provisional estimate and excludes optional add-ons.

(Optional: For the AI model implementing this: do not try to achieve this 
unless I explictly tell you to do so , and you then ask me for confirmation 
## 13. Optional Add-ons

The following features are separate from core requirements.

### A. Scheduling and Task-Launch Overhead — Highest Priority

Each assigned task shall occupy its processor for h preparation time units before computation begins. Default h is zero.

Example: assignment at time 3, h = 1, computation duration = 5. Preparation runs from 3 to 4; computation runs from 4 to 9; successors become eligible after time 9.

Preparation on different processors may overlap. Gray timeline segments shall represent overhead. This models per-processor task-launch cost, not a centralized scheduler queue or communication cost.

This extension shall support experiments on task granularity and D&C base-case thresholds.

For N tasks:

- Original computational work remains W.
- Total launch overhead is N × h.
- Same-model serial baseline is T_1 = W + N × h.
- Speedup is T_1/T_P.
- Useful computation utilization is W/(P × T_P).

For an overhead-aware lower bound, use effective task weights duration(v) + h and recompute work and span. Initial policy priorities may remain based on computational durations; the interface shall state this convention.

### B. Exact Optimal Schedule Solver

An exact solver may search for minimum makespan on very small generated DAGs. Its task-count limit and time budget shall be determined through testing.

It shall distinguish a proven optimum from the best schedule found before timeout. The search shall account for potentially beneficial intentional idle time. Limits shall apply to actual computation-task count.

### C. Measured Task Durations

A benchmark extension may execute predefined backend computations repeatedly and use median measured durations as simulation weights.

It shall not execute arbitrary uploaded code. Results shall be described as server-dependent estimates with variability, rather than exact predictions of concurrent performance. Mapping D&C measurements to split, base-case, and combine costs requires further design.

### D. Size-Dependent D&C Costs

An extension may allow split, combine, and base-case durations to depend on subproblem size, such as split(m) = a × m. Supported functions and parameter limits shall be explicitly defined.
)



## 14. Frontend–Backend Integration Summary 

This section intentionally repeats the integration plan for separate review.

**The application accepts exactly two input forms: Map or Divide-and-Conquer.** The frontend uses HTML/CSS/JavaScript, and the backend uses Python/Flask. Following the TA's recommendation, storage shall be file-based, and the Flask backend shall be hosted on Render. The recommended arrangement is to serve the frontend and API from the same origin.

### 14.1 Simulation Request Flow

1. The user selects Map or D&C.
2. The user enters task durations or D&C parameters, processor count, and scheduling policy.
3. The frontend sends the configuration as JSON using fetch.
4. The backend validates the input and generates the computation DAG.
5. The backend runs the discrete event scheduling simulator.
6. The backend computes work, span, makespan, speedup, and utilization.
7. The backend returns the DAG, execution timeline, and metrics as JSON.
8. The frontend renders the results and supports comparisons between policies.

The backend performs actual graph generation, simulation, and validation. The frontend provides parameter entry and interactive visualization.

### 14.2 Authentication and File-Based Storage Flow

1. The user registers or logs in through the frontend.
2. The backend hashes or verifies the password and establishes the login session.
3. When the user selects Save, the backend associates the experiment with the authenticated user and appends a new record to the storage file.
4. The frontend requests the user's experiment history.
5. The backend reads the accumulated file records, reconstructs current saved data, and checks authentication and ownership before returning records or appending updates or deletion markers.
6. The frontend restores saved inputs and results, and supports rerunning, renaming, and deleting experiments.


Experiment inputs: 
The frontend: collects the selected input form and its parameters. 
The backend: validates them and generates the computation DAG. When the user saves an experiment, the backend appends its input form and parameters to the storage file.


Simulation results: 
The backend: runs the scheduling algorithm and calculates performance metrics. 
The frontend: visualizes the returned DAG, execution timeline, and metrics. Saved simulation results are appended to the storage file.

Registration and login: 
The frontend:  provides registration and login forms. 
The backend:  hashes passwords during registration, verifies them during login, and maintains login sessions. The storage file stores user records containing usernames and password hashes.

Experiment history: 
The frontend: lets users view, load, rename, and delete saved experiments. The backend: reads accumulated file records and appends updates or deletion markers and checks that each experiment belongs to the authenticated user. The storage file stores the association between each user and their experiments.

The project therefore includes meaningful frontend–backend communication and file-based persistence. Accounts make saved experiments available across visits, and backend ownership checks keep each user's records private.




//Since map and D&C allowed only, we no dependency needed to be specified by the user

// questions: 1 persistent file storage details  2 login and security


//scan to be added???