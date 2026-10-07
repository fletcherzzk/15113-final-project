"""Same-origin Flask frontend/API. Run locally with `python app.py`."""

from datetime import timedelta
from functools import wraps
import hmac
import os
from pathlib import Path
import secrets

from flask import Flask, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from lab.auth import AuthLimiter, credentials
from lab.simulation import StructuralError, ValidationError, run_experiment
from lab.storage import ConflictError, EventStore, NotFoundError, StorageError, experiment_name


def create_app(test_config=None):
    app = Flask(__name__)
    production = os.environ.get("APP_ENV") == "production"
    secret = os.environ.get("SECRET_KEY")
    storage = os.environ.get("STORAGE_PATH")
    if production and (not secret or len(secret) < 32):
        raise RuntimeError("Production requires SECRET_KEY with at least 32 characters.")
    if production and (not storage or not Path(storage).is_absolute()):
        raise RuntimeError("Production requires an absolute STORAGE_PATH on a persistent disk.")
    app.config.update(
        SECRET_KEY=secret or secrets.token_hex(32),
        STORAGE_PATH=storage or str(Path(app.root_path) / "storage" / "records.jsonl"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=production,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    # Render terminates HTTPS at its single trusted edge proxy.
    if production:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    store = EventStore(app.config["STORAGE_PATH"])
    limiter = AuthLimiter()
    app.extensions["event_store"] = store
    app.extensions["auth_limiter"] = limiter
    dummy_hash = generate_password_hash(secrets.token_hex(16), method="scrypt:32768:8:1")

    def body():
        if not request.is_json:
            raise ValidationError("Send a JSON request body.")
        raw = request.get_json()
        if not isinstance(raw, dict):
            raise ValidationError("Request body must be a JSON object.")
        return raw

    def identity():
        user_id = session.get("user_id")
        return store.get_user(user_id) if user_id else None

    def public_user(user):
        return {"id": user["id"], "username": user["username"]} if user else None

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    def login_required(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            user = identity()
            if not user:
                return jsonify(error="Log in to manage saved experiments."), 401
            return func(user["id"], *args, **kwargs)
        return wrapped

    @app.before_request
    def protect_requests():
        if production and not request.is_secure and request.path != "/api/health":
            return jsonify(error="HTTPS is required."), 400
        if request.path.startswith("/api/") and request.method in ("POST", "PATCH", "DELETE"):
            expected, received = session.get("csrf_token"), request.headers.get("X-CSRF-Token")
            if not expected or not received or not hmac.compare_digest(expected.encode(), received.encode()):
                return jsonify(error="Session expired. Refresh the page and try again."), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValidationError)
    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(StructuralError)
    def invalid_graph(error):
        return jsonify(error=str(error)), 422

    @app.errorhandler(ConflictError)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(NotFoundError)
    def not_found(error):
        return jsonify(error=str(error)), 404

    @app.errorhandler(StorageError)
    def storage_unavailable(error):
        app.logger.error("Storage unavailable: %s", error)
        return jsonify(error="Saved data is temporarily unavailable. Please try again later."), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/session")
    def current_session():
        return jsonify(user=public_user(identity()), csrf_token=csrf_token())

    def authenticate(register=False):
        raw = body()
        candidate = raw.get("username")
        candidate = candidate[:30] if isinstance(candidate, str) else ""
        if not limiter.allow(request.remote_addr or "unknown", candidate):
            response = jsonify(error="Too many account attempts. Try again in 15 minutes.")
            response.headers["Retry-After"] = "900"
            return response, 429
        username, password = credentials(raw)
        if register:
            user = store.create_user(username, generate_password_hash(password, method="scrypt:32768:8:1"))
        else:
            user = store.find_user(username)
            verified = check_password_hash(user["password_hash"] if user else dummy_hash, password)
            if not user or not verified:
                return jsonify(error="Incorrect username or password."), 401
        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True
        return jsonify(user=public_user(user), csrf_token=csrf_token()), 201 if register else 200

    @app.post("/api/register")
    def register():
        return authenticate(register=True)

    @app.post("/api/login")
    def login():
        return authenticate()

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(user=None, csrf_token=csrf_token())

    @app.post("/api/simulate")
    def simulation():
        return jsonify(run_experiment(body()))

    @app.get("/api/experiments")
    @login_required
    def history(owner_id):
        summaries = [{key: saved[key] for key in ("id", "name", "configuration", "created_at", "simulator_version")}
                     for saved in store.list_experiments(owner_id)]
        return jsonify(experiments=summaries)

    @app.post("/api/experiments")
    @login_required
    def save(owner_id):
        raw = body()
        name = experiment_name(raw.get("name"))
        # Never accept client-supplied results or ownership.
        experiment = run_experiment(raw.get("configuration"))
        return jsonify(store.create_experiment(owner_id, name, experiment)), 201

    @app.get("/api/experiments/<experiment_id>")
    @login_required
    def load(owner_id, experiment_id):
        return jsonify(store.get_experiment(owner_id, experiment_id))

    @app.patch("/api/experiments/<experiment_id>")
    @login_required
    def rename(owner_id, experiment_id):
        return jsonify(store.rename_experiment(owner_id, experiment_id, body().get("name")))

    @app.delete("/api/experiments/<experiment_id>")
    @login_required
    def delete(owner_id, experiment_id):
        store.delete_experiment(owner_id, experiment_id)
        return jsonify(deleted=True)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
