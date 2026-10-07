// Assemble only public assets for Pages. Never upload node_modules or test data.
const fs = require("node:fs");
const path = require("node:path");

function buildPages(apiBaseUrl, destination) {
  if (!apiBaseUrl) throw new Error("Set API_BASE_URL to your Render HTTPS origin (without /api).");
  const url = new URL(apiBaseUrl);
  if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("API_BASE_URL must be an HTTPS origin without a path, credentials, query, or fragment.");
  }
  const source = path.resolve(__dirname, "..");
  fs.mkdirSync(path.join(destination, "static"), { recursive: true });
  const html = fs.readFileSync(path.join(source, "index.html"), "utf8")
    .replace(/connect-src [^;]*;/, `connect-src 'self' ${url.origin};`);
  fs.writeFileSync(path.join(destination, "index.html"), html);
  fs.writeFileSync(path.join(destination, "config.js"), `window.LAB_CONFIG = Object.freeze(${JSON.stringify({ apiBaseUrl: url.origin })});\n`);
  fs.copyFileSync(path.join(source, ".nojekyll"), path.join(destination, ".nojekyll"));
  for (const asset of ["app.js", "styles.css"]) fs.copyFileSync(path.join(source, "static", asset), path.join(destination, "static", asset));
  return url.origin;
}

if (require.main === module) {
  const destination = path.resolve(__dirname, "../../other/artifacts/pages");
  console.log(`Built GitHub Pages assets for ${buildPages(process.env.API_BASE_URL, destination)}`);
}
module.exports = { buildPages };
