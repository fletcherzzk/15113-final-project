"use strict";

const $ = (id) => document.getElementById(id);
const policies = { fixed: "Fixed order", longest: "Longest task first", critical: "Critical path first" };
const types = { map: "Map", split: "Split", base: "Base case", combine: "Combine" };
const state = { csrf: null, user: null, experiment: null, selected: null, authMode: "login", editing: null, pending: false, saving: false };
const presets = {
  nonuniform: [3, 3, 2, 2, 2], uniform: Array(8).fill(3),
  straggler: [1, 1, 1, 1, 12], mixed: [2, 8, 3, 7, 4, 6],
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function svg(tag, attributes = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
  $("notice").hidden = false;
}
function clearNotice() { $("notice").hidden = true; }
function inputError(message) { $("input-error").textContent = message; $("input-error").hidden = !message; }
function format(number, digits = 2) { return Number.isInteger(number) ? String(number) : number.toFixed(digits); }

async function api(path, method = "GET", data) {
  if (method !== "GET" && !state.csrf) throw new Error("The server session is unavailable. Refresh the page and try again.");
  const headers = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = state.csrf;
  if (data !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(`/api${path}`, { method, headers, credentials: "same-origin", body: data === undefined ? undefined : JSON.stringify(data) });
  } catch { throw new Error("Cannot reach the server. Check your connection and try again."); }
  const value = await response.json().catch(() => ({ error: "The server returned an unexpected response." }));
  if (!response.ok) throw new Error(value.error || "The request could not be completed.");
  return value;
}

function integer(id, label, min, max) {
  const value = Number($(id).value);
  if (!$(id).value.trim() || !Number.isInteger(value) || value < min || value > max) throw new Error(`${label} must be an integer from ${min} to ${max}.`);
  return value;
}
function parameters() {
  const form = document.querySelector('input[name="form"]:checked').value;
  if (form === "map") {
    const text = $("durations").value.trim();
    const values = text.split(/[,\s]+/);
    if (values.length < 2 || values.length > 16) throw new Error("Map requires 2–16 task durations.");
    if (values.some((value) => !/^\d+$/.test(value) || Number(value) < 1 || Number(value) > 20)) throw new Error("Every task duration must be an integer from 1 to 20.");
    return { form, parameters: { durations: values.map(Number) }, count: values.length };
  }
  const n = integer("n", "Problem size n", 2, 8);
  const k = integer("k", "Split parameter k", 2, 8);
  const b = integer("b", "Base threshold b", 1, n - 1);
  const countTasks = (m) => {
    if (m <= b) return 1;
    const small = Math.min(Math.ceil(m / k), Math.floor(m / 2));
    return 2 + countTasks(small) + countTasks(m - small);
  };
  return { form, parameters: { n, k, b, split_duration: integer("split-duration", "Split duration", 1, 20), base_duration: integer("base-duration", "Base duration", 1, 20), combine_duration: integer("combine-duration", "Combine duration", 1, 20) }, count: countTasks(n) };
}
function configuration() {
  const input = parameters();
  return { form: input.form, parameters: input.parameters, processors: integer("processors", "Processor count P", 1, input.count - 1), policy: $("policy").value };
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  return value;
}
function isDirty() {
  if (!state.experiment) return false;
  try { return JSON.stringify(canonical(configuration())) !== JSON.stringify(canonical(state.experiment.configuration)); }
  catch { return true; }
}
function refreshDirty() {
  const dirty = isDirty();
  $("stale-note").hidden = !dirty;
  $("save-button").disabled = dirty || state.saving;
  $("save-help").textContent = dirty ? "Run the changed inputs before saving." : state.user ? "Save the displayed configuration and results." : "Log in to save results and revisit them later.";
}
function refreshInputs() {
  const map = document.querySelector('input[name="form"]:checked').value === "map";
  $("map-inputs").hidden = !map;
  $("dc-inputs").hidden = map;
  for (const node of $("map-inputs").querySelectorAll("input, select, textarea")) node.disabled = !map;
  for (const node of $("dc-inputs").querySelectorAll("input")) node.disabled = map;
  const n = Number($("n").value);
  if (Number.isInteger(n) && n >= 2 && n <= 8) {
    $("b").max = String(n - 1);
    $("b-help").textContent = `1–${n - 1} · a call stops when its size ≤ b`;
  }
  const help = { fixed: "Earlier numeric task ID first.", longest: "Larger duration first. Ties use task ID.", critical: "Larger remaining dependency-path duration first. Ties use task ID." };
  $("policy-help").textContent = help[$("policy").value];
  let validParameters = false;
  try {
    const input = parameters();
    $("task-count").textContent = String(input.count).padStart(2, "0");
    $("processors").max = String(input.count - 1);
    $("processor-help").textContent = `Valid range: 1–${input.count - 1} processors (P < N).`;
    validParameters = true;
    configuration();
    inputError("");
  } catch (error) {
    if (!validParameters) {
      $("task-count").textContent = "—";
      $("processor-help").textContent = "P must be at least 1 and smaller than the generated task count.";
    }
    inputError(error.message);
  }
  refreshDirty();
}

function taskActivation(node, task) {
  node.setAttribute("role", "button");
  node.setAttribute("tabindex", "0");
  const entry = state.experiment.results.timeline.find((e) => e.task_id === task.id);
  node.setAttribute("aria-label", `Task T${task.id}, ${types[task.type]}, duration ${task.duration}, processor ${entry.processor_id}, time ${entry.start} to ${entry.end}`);
  node.dataset.taskId = task.id;
  const select = () => selectTask(task.id);
  node.addEventListener("click", select);
  node.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
}
function selectTask(id) {
  state.selected = id;
  const task = state.experiment.dag.find((task) => task.id === id);
  const assignment = state.experiment.results.timeline.find((entry) => entry.task_id === id);
  const detail = element("div", "detail-grid");
  const fields = [
    ["Task", `T${id} · ${types[task.type]}${task.size === null ? "" : ` · size ${task.size}`}`],
    ["Duration / remaining path", `${task.duration} / ${task.rank} time units`],
    ["Dependencies", task.dependencies.length ? task.dependencies.map((dep) => `T${dep}`).join(", ") : "None · initially ready"],
    ["Processor", `P${assignment.processor_id}`], ["Start → end", `${assignment.start} → ${assignment.end}`],
    ["Execution status", "Completed"],
  ];
  for (const [label, value] of fields) { const cell = element("div"); cell.append(element("strong", "", label), element("span", "", value)); detail.append(cell); }
  $("task-detail").replaceChildren(detail);
  for (const node of document.querySelectorAll("[data-task-id]")) {
    const selected = Number(node.dataset.taskId) === id;
    node.classList.toggle("selected", selected);
    node.setAttribute("aria-pressed", String(selected));
  }
}

function renderMetrics() {
  const m = state.experiment.results.metrics;
  const values = [["Completion time", format(m.makespan), "simulated time units", "highlight"], ["Speedup", `${format(m.speedup)}×`, "relative to one processor", ""], ["Utilization", `${format(m.utilization * 100, 1)}%`, "of available processor time", ""], ["Lower bound", format(m.lower_bound), "max(W/P, S) · may be unattainable", ""], ["Work W", format(m.work), "total computation", ""], ["Span S", format(m.span), "longest dependency path", ""], ["Parallelism", format(m.average_parallelism), "W/S", ""], ["Processors", String(state.experiment.configuration.processors), `${state.experiment.dag.length} computation tasks`, ""]];
  $("metrics").replaceChildren(...values.map(([label, value, help, className]) => { const card = element("div", `metric ${className}`); card.append(element("span", "", label), element("strong", "", value), element("small", "", help)); return card; }));
}
function renderTimeline() {
  const { results, configuration: config, dag } = state.experiment;
  const end = results.metrics.makespan;
  const width = 820, left = 57, right = 803, rowHeight = 47, top = 37;
  const height = top + config.processors * rowHeight + 20;
  const x = (time) => left + time / end * (right - left);
  const canvas = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "timeline-svg", role: "group", "aria-label": `Aligned processor timeline from time 0 to ${end}` });
  const defs = svg("defs"), pattern = svg("pattern", { id: "idle-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse" });
  pattern.append(svg("rect", { width: 6, height: 6, fill: "#f8f9f4" }), svg("path", { d: "M0 6L6 0", stroke: "#e1e5d9", "stroke-width": 1 })); defs.append(pattern); canvas.append(defs);
  const step = Math.max(1, Math.ceil(end / 10));
  const ticks = [];
  for (let time = 0; time < end; time += step) ticks.push(time);
  ticks.push(end);
  for (const time of ticks) {
    canvas.append(svg("line", { x1: x(time), x2: x(time), y1: 27, y2: height - 14, class: "grid-line" }));
    if (time !== end && end - time < step * 0.5) continue;
    canvas.append(svg("text", { x: x(time), y: 15, "text-anchor": "middle", class: "tick-label" }, time));
  }
  for (let processor = 1; processor <= config.processors; processor++) {
    const y = top + (processor - 1) * rowHeight;
    canvas.append(svg("text", { x: 0, y: y + 21, class: "processor-label" }, `P${processor}`));
    canvas.append(svg("rect", { x: left, y, width: right - left, height: 32, rx: 4, fill: "#f8f9f4", class: "processor-track" }));
  }
  for (const idle of results.idle_intervals) {
    const box = svg("rect", { x: x(idle.start), y: top + (idle.processor_id - 1) * rowHeight, width: x(idle.end) - x(idle.start), height: 32, fill: "url(#idle-hatch)" });
    box.append(svg("title", {}, `P${idle.processor_id} idle: ${idle.start}–${idle.end}`)); canvas.append(box);
  }
  const byId = new Map(dag.map((task) => [task.id, task]));
  for (const entry of results.timeline) {
    const task = byId.get(entry.task_id), y = top + (entry.processor_id - 1) * rowHeight;
    const node = svg("g", { class: "task-node" });
    const taskWidth = x(entry.end) - x(entry.start);
    node.append(svg("rect", { x: x(entry.start) + 1, y, width: Math.max(taskWidth - 2, 1), height: 32, rx: 4, class: `task-${task.type}` }));
    node.append(svg("title", {}, `T${task.id} · ${types[task.type]} · P${entry.processor_id} · ${entry.start}–${entry.end}`));
    if (taskWidth >= 26) node.append(svg("text", { x: x(entry.start) + taskWidth / 2, y: y + 21, "text-anchor": "middle", class: "task-label" }, `T${task.id}`));
    taskActivation(node, task); canvas.append(node);
  }
  $("timeline").replaceChildren(canvas);
  $("timeline-duration").textContent = `0 → ${end} time units`;
  const kinds = [...new Set(dag.map((task) => task.type)), "idle"];
  $("legend").replaceChildren(...kinds.map((kind) => { const item = element("span", "legend-item"); item.append(element("i", `swatch ${kind}`), document.createTextNode(types[kind] || "Idle")); return item; }));
}

function renderComparison() {
  const experiment = state.experiment;
  const minimum = Math.min(...Object.values(experiment.comparisons).map((result) => result.metrics.makespan));
  const rows = Object.entries(policies).map(([policy, label]) => {
    const result = experiment.comparisons[policy], row = element("tr", policy === experiment.configuration.policy ? "selected-policy" : "");
    const name = element("td", "", label);
    if (result.metrics.makespan === minimum) name.append(element("span", "fastest", "FASTEST HERE"));
    row.append(name, element("td", "", `${result.metrics.makespan} units`), element("td", "", `${format(result.metrics.speedup)}×`), element("td", "", `${format(result.metrics.utilization * 100, 1)}%`));
    const action = element("td"), button = element("button", "inspect-button", policy === experiment.configuration.policy ? "Viewing" : "View");
    button.setAttribute("aria-label", `View ${label} schedule`);
    button.setAttribute("aria-pressed", String(policy === experiment.configuration.policy));
    button.addEventListener("click", () => { experiment.configuration.policy = policy; experiment.results = experiment.comparisons[policy]; $("policy").value = policy; renderResults(); refreshInputs(); });
    action.append(button); row.append(action); return row;
  });
  $("comparison").replaceChildren(...rows);
  $("comparison-note").textContent = "Fastest here compares these three heuristics; it does not establish an optimal schedule." + (experiment.configuration.form === "map" ? " For independent Map tasks, longest task and critical path priorities are equivalent." : "");
}

function renderDag() {
  const tasks = state.experiment.dag, layers = [], levels = new Map();
  for (const task of tasks) { const level = Math.max(-1, ...task.dependencies.map((dep) => levels.get(dep))) + 1; levels.set(task.id, level); (layers[level] ||= []).push(task); }
  const width = Math.max(600, Math.max(...layers.map((layer) => layer.length)) * 100 + 30), height = layers.length * 86 + 20;
  const canvas = svg("svg", { viewBox: `0 0 ${width} ${height}`, width, height, class: "dag-svg", role: "group", "aria-label": "Generated computation dependency graph" });
  const defs = svg("defs"), marker = svg("marker", { id: "dag-arrow", markerWidth: 7, markerHeight: 7, refX: 6, refY: 3.5, orient: "auto" });
  marker.append(svg("path", { d: "M0 0L7 3.5L0 7Z", fill: "#a4b3a7" })); defs.append(marker); canvas.append(defs);
  const positions = new Map();
  layers.forEach((layer, level) => layer.forEach((task, index) => positions.set(task.id, { x: (index + 0.5) * width / layer.length, y: 10 + level * 86 })));
  for (const task of tasks) {
    const pos = positions.get(task.id);
    for (const dep of task.dependencies) {
      const parent = positions.get(dep);
      canvas.append(svg("path", { d: `M${parent.x} ${parent.y + 47}C${parent.x} ${parent.y + 65},${pos.x} ${pos.y - 18},${pos.x} ${pos.y - 3}`, class: "dag-edge", "marker-end": "url(#dag-arrow)" }));
    }
  }
  for (const task of tasks) {
    const pos = positions.get(task.id), node = svg("g", { class: "task-node" });
    node.append(svg("rect", { x: pos.x - 45, y: pos.y, width: 90, height: 47, rx: 6, class: `task-${task.type}` }), svg("text", { x: pos.x, y: pos.y + 18, "text-anchor": "middle", class: "dag-label" }, `T${task.id} · ${types[task.type]}`), svg("text", { x: pos.x, y: pos.y + 35, "text-anchor": "middle", class: "dag-subtitle" }, `${task.duration} units${task.size === null ? "" : ` · m=${task.size}`}`));
    taskActivation(node, task); canvas.append(node);
  }
  $("dag").replaceChildren(canvas);
}

function renderResults() {
  $("empty-state").hidden = true; $("result-content").hidden = false;
  const config = state.experiment.configuration;
  $("result-label").textContent = `${config.form === "map" ? "MAP" : "D&C"} · ${policies[config.policy]} · ${config.processors} processors`;
  renderMetrics(); renderTimeline(); renderComparison(); renderDag();
  if (state.selected && state.experiment.dag.some((task) => task.id === state.selected)) selectTask(state.selected);
  else { state.selected = null; $("task-detail").textContent = "Select a task on the timeline or dependency graph."; }
  refreshDirty();
}
async function run() {
  let config;
  try { config = configuration(); inputError(""); } catch (error) { inputError(error.message); return; }
  if (state.pending) return;
  state.pending = true; $("run-button").disabled = true; $("run-button").textContent = "Simulating…"; clearNotice();
  try { state.experiment = await api("/simulate", "POST", config); state.selected = null; renderResults(); }
  catch (error) { notice(error.message, true); }
  finally { state.pending = false; $("run-button").disabled = false; $("run-button").textContent = "Run simulation ↗"; }
}
function restore(config) {
  document.querySelector(`input[name="form"][value="${config.form}"]`).checked = true;
  if (config.form === "map") { $("durations").value = config.parameters.durations.join(", "); $("preset").value = "custom"; }
  else for (const [key, id] of Object.entries({ n: "n", k: "k", b: "b", split_duration: "split-duration", base_duration: "base-duration", combine_duration: "combine-duration" })) $(id).value = config.parameters[key];
  $("processors").value = config.processors; $("policy").value = config.policy; refreshInputs();
}

function renderAccount() {
  $("account-label").textContent = state.user ? state.user.username : "Guest session";
  $("account-button").hidden = Boolean(state.user); $("logout-button").hidden = !state.user;
  $("refresh-history").hidden = !state.user; refreshDirty();
}
function authMode(mode) {
  state.authMode = mode; $("auth-title").textContent = mode === "login" ? "Welcome back" : "Make room for discovery";
  $("auth-submit").textContent = mode === "login" ? "Log in" : "Create account";
  $("password").autocomplete = mode === "login" ? "current-password" : "new-password";
  $("login-tab").classList.toggle("active", mode === "login"); $("register-tab").classList.toggle("active", mode === "register"); $("auth-error").hidden = true;
}

async function refreshHistory() {
  if (!state.user) { $("history").replaceChildren(element("p", "help", "Log in to build your private experiment collection.")); return; }
  const owner = state.user.id;
  const data = await api("/experiments");
  if (state.user?.id !== owner) return;
  if (!data.experiments.length) { $("history").replaceChildren(element("p", "help", "No saved experiments yet. Run one above and give it a name.")); return; }
  $("history").replaceChildren(...data.experiments.map((saved) => {
    const card = element("article", "history-card"), config = saved.configuration;
    card.append(element("h3", "", saved.name), element("p", "history-meta", `${config.form === "map" ? "Map" : "Divide & conquer"} · ${config.processors} processors · ${policies[config.policy]}`), element("p", "history-meta", new Date(saved.created_at).toLocaleString()));
    const actions = element("div", "history-actions");
    for (const action of ["Load", "Rename", "Delete"]) {
      const button = element("button", "", action); button.setAttribute("aria-label", `${action} ${saved.name}`);
      button.addEventListener("click", async () => {
        if (action !== "Load") { openEdit(saved, action.toLowerCase()); return; }
        button.disabled = true;
        try { const value = await api(`/experiments/${saved.id}`); state.experiment = value.experiment; state.selected = null; restore(value.configuration); renderResults(); $("experiment-name").value = value.name; notice(`Loaded “${value.name}”. Saved inputs and results are restored.`); $("result-content").scrollIntoView({ block: "start" }); }
        catch (error) { notice(error.message, true); } finally { button.disabled = false; }
      });
      actions.append(button);
    }
    card.append(actions); return card;
  }));
}
function openEdit(saved, action) {
  state.editing = { saved, action };
  const remove = action === "delete";
  $("edit-title").textContent = remove ? "Delete experiment?" : "Rename experiment";
  $("edit-description").textContent = remove ? `“${saved.name}” will be removed from your saved experiments.` : "Give this experiment a new name.";
  $("edit-name").hidden = remove; $("edit-name-label").hidden = remove; $("edit-name").required = !remove; $("edit-name").value = saved.name;
  $("edit-submit").textContent = remove ? "Delete" : "Rename"; $("edit-error").hidden = true; $("edit-dialog").showModal();
}

$("experiment-form").addEventListener("submit", (event) => { event.preventDefault(); run(); });
$("experiment-form").addEventListener("input", (event) => { if (event.target.id === "durations") $("preset").value = "custom"; refreshInputs(); });
$("experiment-form").addEventListener("change", () => refreshInputs());
$("preset").addEventListener("change", () => { const durations = presets[$("preset").value]; if (durations) $("durations").value = durations.join(", "); refreshInputs(); });
$("account-button").addEventListener("click", () => { authMode("login"); $("auth-dialog").showModal(); });
$("login-tab").addEventListener("click", () => authMode("login"));
$("register-tab").addEventListener("click", () => authMode("register"));
for (const button of document.querySelectorAll("[data-close]")) button.addEventListener("click", () => $(button.dataset.close).close());
$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault(); $("auth-submit").disabled = true; $("auth-error").hidden = true;
  try {
    const value = await api(`/${state.authMode}`, "POST", { username: $("username").value, password: $("password").value });
    state.user = value.user; state.csrf = value.csrf_token; $("password").value = ""; $("auth-dialog").close(); renderAccount();
    notice(`Signed in as ${state.user.username}.`); await refreshHistory();
  } catch (error) { $("auth-error").textContent = error.message; $("auth-error").hidden = false; }
  finally { $("auth-submit").disabled = false; }
});
$("logout-button").addEventListener("click", async () => {
  $("logout-button").disabled = true;
  try { const value = await api("/logout", "POST", {}); state.user = null; state.csrf = value.csrf_token; renderAccount(); await refreshHistory(); notice("You are logged out. You can keep running experiments as a guest."); }
  catch (error) { notice(error.message, true); } finally { $("logout-button").disabled = false; }
});
$("save-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.experiment || isDirty() || state.saving) return;
  if (!state.user) { authMode("login"); $("auth-dialog").showModal(); return; }
  state.saving = true; $("save-button").disabled = true;
  try { const saved = await api("/experiments", "POST", { name: $("experiment-name").value, configuration: state.experiment.configuration }); notice(`Saved “${saved.name}”.`); await refreshHistory(); }
  catch (error) { notice(error.message, true); } finally { state.saving = false; refreshDirty(); }
});
$("refresh-history").addEventListener("click", () => refreshHistory().catch((error) => notice(error.message, true)));
$("edit-form").addEventListener("submit", async (event) => {
  event.preventDefault(); $("edit-submit").disabled = true;
  try {
    const { action, saved } = state.editing;
    await api(`/experiments/${saved.id}`, action === "delete" ? "DELETE" : "PATCH", action === "rename" ? { name: $("edit-name").value } : undefined);
    $("edit-dialog").close(); notice(action === "delete" ? "Experiment deleted." : "Experiment renamed."); await refreshHistory();
  } catch (error) { $("edit-error").textContent = error.message; $("edit-error").hidden = false; }
  finally { $("edit-submit").disabled = false; }
});

async function initialize() {
  refreshInputs();
  try { const session = await api("/session"); state.csrf = session.csrf_token; state.user = session.user; renderAccount(); await run(); await refreshHistory(); }
  catch (error) { notice(error.message, true); }
}
initialize();
