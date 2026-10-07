// Runs the real frontend JavaScript against an isolated Flask server.
// JSDOM verifies DOM behavior; it does not replace a browser layout review.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const http = require("node:http");
const { spawn } = require("node:child_process");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "../..");
let base, frontendBase, staticServer, server, serverLog = "";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(predicate, message) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await delay(20);
  }
  throw new Error(`Timed out: ${message}\n${serverLog}`);
}

before(async () => {
  const probe = net.createServer();
  await new Promise((resolve) => probe.listen(0, "127.0.0.1", resolve));
  const port = probe.address().port;
  await new Promise((resolve) => probe.close(resolve));
  base = `http://127.0.0.1:${port}`;
  const publicFiles = { "": "index.html", "config.js": "config.js", "static/app.js": "static/app.js", "static/styles.css": "static/styles.css" };
  staticServer = http.createServer((request, response) => {
    const pathname = new URL(request.url, "http://localhost").pathname;
    const prefix = "/15113-final-project/";
    const file = pathname.startsWith(prefix) ? publicFiles[pathname.slice(prefix.length)] : undefined;
    if (!file) { response.writeHead(404).end(); return; }
    response.setHeader("Content-Type", file.endsWith(".html") ? "text/html; charset=utf-8" : file.endsWith(".css") ? "text/css" : "application/javascript");
    response.end(file === "config.js" ? `window.LAB_CONFIG = ${JSON.stringify({ apiBaseUrl: base })};` : fs.readFileSync(path.join(root, "frontend", file)));
  });
  await new Promise((resolve) => staticServer.listen(0, "127.0.0.1", resolve));
  const frontendOrigin = `http://127.0.0.1:${staticServer.address().port}`;
  frontendBase = `${frontendOrigin}/15113-final-project/`;
  fs.mkdirSync(path.join(root, "other", "artifacts"), { recursive: true });
  const directory = fs.mkdtempSync(path.join(root, "other", "artifacts", "ui-"));
  const venv = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const python = process.env.PYTHON_EXECUTABLE || (fs.existsSync(venv) ? venv : "python");
  server = spawn(python, ["-c", `from app import create_app; create_app().run(host='127.0.0.1', port=${port})`], {
    cwd: path.join(root, "backend"), windowsHide: true,
    env: { ...process.env, APP_ENV: "development", SECRET_KEY: "isolated-frontend-test-secret", FRONTEND_ORIGINS: frontendOrigin, STORAGE_PATH: path.join(directory, "records.jsonl"), PYTHONDONTWRITEBYTECODE: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.on("error", (error) => { serverLog += error.message; });
  server.stdout.on("data", (data) => { serverLog += data; });
  server.stderr.on("data", (data) => { serverLog += data; });
  await waitFor(async () => {
    if (server.exitCode !== null) throw new Error(`Flask server exited: ${serverLog}`);
    try { return (await fetch(`${base}/api/health`)).ok; } catch { return false; }
  }, "test server startup");
});
after(async () => { if (server) server.kill(); if (staticServer) await new Promise((resolve) => staticServer.close(resolve)); });

async function openPage(savedSession) {
  const html = await (await fetch(frontendBase)).text();
  const dom = new JSDOM(html, { url: frontendBase, runScripts: "outside-only", pretendToBeVisual: true });
  const window = dom.window;
  const requests = [];
  if (savedSession) window.sessionStorage.setItem(`parallel-lab.session:${base}`, savedSession);
  window.fetch = async (url, init = {}) => {
    assert.equal(new URL(url).origin, base, "API requests target the independently hosted backend");
    assert.equal(init.credentials, "omit", "Login must not depend on third-party cookies");
    const headers = { ...init.headers, Origin: window.location.origin };
    assert.equal(headers.Cookie, undefined);
    const custom = Object.keys(init.headers).filter((key) => ["authorization", "content-type", "x-csrf-token"].includes(key.toLowerCase()));
    if (custom.length) {
      const preflight = await fetch(url, { method: "OPTIONS", headers: {
        Origin: window.location.origin, "Access-Control-Request-Method": init.method,
        "Access-Control-Request-Headers": custom.join(", "),
      } });
      assert.equal(preflight.status, 204, "Browser CORS preflight succeeds");
      assert.equal(preflight.headers.get("Access-Control-Allow-Origin"), window.location.origin);
    }
    const response = await fetch(url, { ...init, headers });
    assert.equal(response.headers.get("Access-Control-Allow-Origin"), window.location.origin);
    assert.match(response.headers.get("Access-Control-Expose-Headers"), /X-Session-Token/);
    assert.equal(response.headers.get("set-cookie"), null);
    requests.push({ url, ...init });
    return response;
  };
  // Native modal/focus/layout behavior is outside JSDOM's scope.
  window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  window.HTMLDialogElement.prototype.close = function () { this.open = false; };
  window.HTMLElement.prototype.scrollIntoView = function () {};
  window.eval(await (await fetch(new URL("config.js", frontendBase))).text());
  window.eval(await (await fetch(new URL("static/app.js", frontendBase))).text());
  const get = (id) => window.document.getElementById(id);
  await waitFor(() => !get("result-content").hidden && !get("run-button").disabled, "initial simulation");
  return { dom, window, get, requests };
}
function input(page, id, value) {
  page.get(id).value = String(value);
  page.get(id).dispatchEvent(new page.window.Event("input", { bubbles: true }));
}
function submit(page, id) {
  page.get(id).dispatchEvent(new page.window.Event("submit", { bubbles: true, cancelable: true }));
}
async function run(page) {
  submit(page, "experiment-form");
  await waitFor(() => !page.get("run-button").disabled && page.get("stale-note").hidden, "simulation response");
}

test("initial Map results, shared axis, task selection, and JSON key-order equality", async () => {
  const page = await openPage();
  try {
    assert.equal(page.get("metrics").querySelector("strong").textContent, "7");
    assert.equal(page.get("metrics").children.length, 8);
    assert.equal(page.get("stale-note").hidden, true);
    assert.equal(page.get("save-button").disabled, false);
    assert.equal(page.get("comparison").children.length, 3);
    const canvas = page.get("timeline").querySelector("svg");
    assert.equal(canvas.querySelectorAll(".processor-label").length, 2);
    const tracks = [...canvas.querySelectorAll(".processor-track")];
    assert.equal(tracks.length, 2);
    assert.equal(tracks[0].getAttribute("x"), tracks[1].getAttribute("x"));
    assert.equal(tracks[0].getAttribute("width"), tracks[1].getAttribute("width"));
    const task = canvas.querySelector("[data-task-id='1']");
    task.dispatchEvent(new page.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    assert.equal(task.getAttribute("aria-pressed"), "true");
    assert.match(page.get("task-detail").textContent, /T1 · Map/);
    assert.match(page.get("task-detail").textContent, /0 → 3/);
    assert.equal(page.get("dag-panel").open, false);
    assert.equal(page.get("timeline").hidden, false);
    assert.equal(page.window.document.querySelector(".brand").href, frontendBase);
    assert.equal(new URL(page.window.document.querySelector("link[rel='stylesheet']").href).pathname, "/15113-final-project/static/styles.css");
    assert.ok(page.requests.find((request) => request.method === "POST" && request.headers.Authorization && request.headers["X-CSRF-Token"]));
  } finally { page.dom.window.close(); }
});

test("presets, stale input handling, rerun, and policy inspection", async () => {
  const page = await openPage();
  try {
    page.get("preset").value = "uniform";
    page.get("preset").dispatchEvent(new page.window.Event("change", { bubbles: true }));
    assert.equal(page.get("durations").value, "3, 3, 3, 3, 3, 3, 3, 3");
    assert.equal(page.get("stale-note").hidden, false);
    assert.equal(page.get("save-button").disabled, true);
    assert.match(page.get("processor-help").textContent, /1–7/);
    await run(page);
    assert.equal(page.get("metrics").querySelector("strong").textContent, "12");
    page.get("comparison").querySelector("button").click();
    assert.equal(page.get("policy").value, "fixed");
    assert.equal(page.get("stale-note").hidden, true);
    assert.equal(page.get("save-button").disabled, false);
    assert.match(page.get("result-label").textContent, /Fixed order/);
  } finally { page.dom.window.close(); }
});

test("D&C generated task count, joins, collapsible graph, and validation", async () => {
  const page = await openPage();
  try {
    const radio = page.window.document.querySelector('input[name="form"][value="dc"]');
    radio.checked = true; radio.dispatchEvent(new page.window.Event("change", { bubbles: true }));
    input(page, "k", 3); input(page, "processors", 3);
    assert.equal(page.get("map-inputs").hidden, true);
    assert.equal(page.get("durations").disabled, true);
    assert.equal(page.get("dc-inputs").hidden, false);
    assert.equal(page.get("task-count").textContent, "22");
    assert.match(page.get("processor-help").textContent, /1–21/);
    await run(page);
    assert.equal(page.get("stale-note").hidden, true);
    assert.equal(page.get("timeline").querySelectorAll(".task-node").length, 22);
    assert.equal(page.get("timeline").querySelectorAll(".processor-label").length, 3);
    page.get("dag-panel").open = true;
    assert.equal(page.get("dag").querySelectorAll(".task-node").length, 22);
    page.get("dag").querySelector("[data-task-id='22']").dispatchEvent(new page.window.MouseEvent("click", { bubbles: true }));
    assert.match(page.get("task-detail").textContent, /Combine/);
    assert.match(page.get("task-detail").textContent, /DependenciesT\d+, T\d+/);
    page.get("dag-panel").open = false;
    assert.ok(page.get("timeline").querySelector("svg"));
    input(page, "processors", 22);
    assert.match(page.get("input-error").textContent, /1 to 21/);
    assert.equal(page.get("task-count").textContent, "22");
    assert.match(page.get("processor-help").textContent, /1–21/);
    assert.equal(page.get("save-button").disabled, true);
    input(page, "n", 2);
    assert.equal(page.get("b").max, "1");
    input(page, "b", 2);
    assert.match(page.get("input-error").textContent, /Base threshold b/);
  } finally { page.dom.window.close(); }
});

test("registration, private save/load/rename/delete, safe names, logout and login", async () => {
  const page = await openPage();
  try {
    const username = `test_${Date.now()}`;
    page.get("account-button").click(); page.get("register-tab").click();
    input(page, "username", username); input(page, "password", "test-password-123"); submit(page, "auth-form");
    await waitFor(() => page.get("logout-button").hidden === false, "registration");
    await waitFor(() => page.get("history").textContent.includes("No saved experiments"), "empty authenticated history");
    const name = '<img src=x onerror="alert(1)">';
    input(page, "experiment-name", name); submit(page, "save-form");
    await waitFor(() => page.get("history").querySelector(".history-card"), "save history");
    assert.equal(page.get("history").querySelector("h3").textContent, name);
    assert.equal(page.get("history").querySelectorAll("img").length, 0);
    const storedToken = page.window.sessionStorage.getItem(`parallel-lab.session:${base}`);
    assert.ok(storedToken);
    const reloaded = await openPage(storedToken);
    try {
      await waitFor(() => reloaded.get("history").querySelector(".history-card"), "login and private history survive a frontend reload");
      assert.equal(reloaded.get("account-label").textContent, username);
      assert.equal(reloaded.get("history").querySelector("h3").textContent, name);
    } finally { reloaded.dom.window.close(); }
    input(page, "durations", "1, 1, 1");
    page.get("history").querySelector("button").click();
    await waitFor(() => page.get("durations").value === "3, 3, 2, 2, 2", "saved input restoration");
    assert.equal(page.get("metrics").querySelector("strong").textContent, "7");
    assert.equal(page.get("stale-note").hidden, true);
    page.get("history").querySelectorAll("button")[1].click(); input(page, "edit-name", "Renamed experiment"); submit(page, "edit-form");
    await waitFor(() => page.get("history").querySelector("h3")?.textContent === "Renamed experiment", "rename");
    page.get("history").querySelectorAll("button")[2].click();
    assert.equal(page.get("edit-title").textContent, "Delete experiment?");
    submit(page, "edit-form");
    await waitFor(() => page.get("history").textContent.includes("No saved experiments"), "deletion");
    page.get("logout-button").click();
    await waitFor(() => page.get("account-button").hidden === false, "logout");
    assert.match(page.get("history").textContent, /Log in/);
    page.get("account-button").click(); input(page, "password", "test-password-123"); submit(page, "auth-form");
    await waitFor(() => page.get("logout-button").hidden === false && !page.get("auth-submit").disabled, "login with rotated CSRF token and completed history refresh");
  } finally { page.dom.window.close(); }
});

test("failed fetch displays an actionable error and releases the run button", async () => {
  const page = await openPage();
  try {
    page.window.fetch = async () => { throw new Error("offline"); };
    submit(page, "experiment-form");
    await waitFor(() => !page.get("run-button").disabled, "failed simulation completion");
    assert.equal(page.get("notice").hidden, false);
    assert.match(page.get("notice").textContent, /Cannot reach the server/);
  } finally { page.dom.window.close(); }
});
