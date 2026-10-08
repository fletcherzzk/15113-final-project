// Local development uses Flask on port 5000; hosted pages use the Render API.
// The Pages build replaces this file with its configured API_BASE_URL.
window.LAB_CONFIG = Object.freeze({
  apiBaseUrl: ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://127.0.0.1:5000"
    : "https://parallel-scheduling-lab.onrender.com",
});
