// Local development default. The Pages build replaces this file with API_BASE_URL.
// Production must point to your Render HTTPS origin; this contains no secrets.
window.LAB_CONFIG = Object.freeze({
  apiBaseUrl: ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://127.0.0.1:5000"
    : "",
});
