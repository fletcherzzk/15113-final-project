const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { buildPages } = require("../scripts/build-pages.cjs");

const artifacts = path.resolve(__dirname, "../../other/artifacts");
fs.mkdirSync(artifacts, { recursive: true });

test("Pages build contains only static public assets and the configured HTTPS API", () => {
  const output = fs.mkdtempSync(path.join(artifacts, "pages-test-"));
  assert.equal(buildPages("https://test-api.onrender.com/", output), "https://test-api.onrender.com");
  assert.deepEqual(fs.readdirSync(output).sort(), [".nojekyll", "config.js", "index.html", "static"]);
  assert.deepEqual(fs.readdirSync(path.join(output, "static")).sort(), ["app.js", "styles.css"]);
  const html = fs.readFileSync(path.join(output, "index.html"), "utf8");
  const config = fs.readFileSync(path.join(output, "config.js"), "utf8");
  assert.match(config, /https:\/\/test-api\.onrender\.com/);
  assert.match(html, /connect-src 'self' https:\/\/test-api\.onrender\.com;/);
  assert.ok(!html.includes("127.0.0.1"));
  assert.ok(!html.includes("{{") && !html.includes("url_for"));
  assert.ok(html.includes('href="./static/styles.css"') && html.includes('src="./config.js"'));
});

test("Pages build rejects missing, non-HTTPS, and non-origin API addresses", () => {
  const output = fs.mkdtempSync(path.join(artifacts, "pages-invalid-"));
  for (const url of ["", "http://localhost:5000", "https://example.com/api", "https://example.com/?secret=x", "https://example.com/#fragment", "https://user:password@example.com", "invalid"]) {
    assert.throws(() => buildPages(url, output));
  }
  assert.deepEqual(fs.readdirSync(output), []);
});
