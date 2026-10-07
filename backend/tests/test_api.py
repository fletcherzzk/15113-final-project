import json

import pytest

from app import create_app
from lab.auth import AuthLimiter


class APIClient:
    """Emulate a frontend retaining the session response header, without cookies."""

    def __init__(self, client):
        self.client = client
        self.session_token = None

    def request(self, method, path, **kwargs):
        headers = {"Origin": "http://127.0.0.1:8000", **kwargs.pop("headers", {})}
        if self.session_token:
            headers.setdefault("Authorization", f"Bearer {self.session_token}")
        response = self.client.open(path, method=method, headers=headers, **kwargs)
        if "X-Session-Token" in response.headers:
            self.session_token = response.headers["X-Session-Token"] or None
        return response

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def options(self, path, **kwargs):
        return self.request("OPTIONS", path, **kwargs)


CONFIG = {"form": "map", "parameters": {"durations": [3, 3, 2, 2, 2]}, "processors": 2, "policy": "longest"}


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-key", "STORAGE_PATH": str(tmp_path / "records.jsonl")})
    raw_client = app.test_client
    app.test_client = lambda: APIClient(raw_client(use_cookies=False))
    return app


def token(client):
    return {"X-CSRF-Token": client.get("/api/session").json["csrf_token"]}


def account(client, username="alice", password="password123"):
    response = client.post("/api/register", json={"username": username, "password": password}, headers=token(client))
    assert response.status_code == 201
    return {"X-CSRF-Token": response.json["csrf_token"]}


def test_guest_simulation_and_authoritative_validation(app):
    client = app.test_client()
    headers = token(client)
    result = client.post("/api/simulate", json=CONFIG, headers=headers)
    assert result.status_code == 200
    assert result.json["results"]["metrics"]["makespan"] == 7
    assert client.get("/api/experiments").status_code == 401
    assert client.post("/api/experiments", json={"name": "Guest", "configuration": CONFIG}, headers=headers).status_code == 401
    assert client.post("/api/simulate", json={**CONFIG, "processors": 5}, headers=headers).status_code == 400
    assert client.post("/api/simulate", json=[CONFIG], headers=headers).status_code == 400
    assert client.post("/api/simulate", data="{bad", content_type="application/json", headers=headers).status_code == 400
    assert client.post("/api/simulate", data="{}", headers=headers).status_code == 400


def test_account_lifecycle_password_hashing_and_csrf(app):
    client = app.test_client()
    old = token(client)
    headers = account(client)
    assert old != headers
    assert client.post("/api/logout", json={}, headers=old).status_code == 403
    assert client.get("/api/session").json["user"]["username"] == "alice"
    content = app.extensions["event_store"].path.read_text()
    assert "password123" not in content
    assert json.loads(content)["data"]["password_hash"].startswith("scrypt:")
    logout = client.post("/api/logout", json={}, headers=headers)
    assert logout.status_code == 200
    headers = {"X-CSRF-Token": logout.json["csrf_token"]}
    assert client.get("/api/session").json["user"] is None
    assert client.post("/api/login", json={"username": "alice", "password": "incorrect"}, headers=headers).status_code == 401
    assert client.post("/api/login", json={"username": "nobody", "password": "incorrect"}, headers=headers).status_code == 401
    login = client.post("/api/login", json={"username": "ALICE", "password": "password123"}, headers=headers)
    assert login.status_code == 200
    assert login.headers["X-Session-Token"]
    assert "Set-Cookie" not in login.headers
    assert "password_hash" not in str(login.json)
    assert client.post("/api/register", json={"username": "Alice", "password": "password123"}, headers={"X-CSRF-Token": login.json["csrf_token"]}).status_code == 409


def test_private_experiment_crud_and_restart(app):
    alice, bob = app.test_client(), app.test_client()
    alice_headers, bob_headers = account(alice), account(bob, "bob")
    saved = alice.post("/api/experiments", json={"name": "First", "configuration": CONFIG, "owner_id": "bob", "experiment": {"fake": True}}, headers=alice_headers)
    assert saved.status_code == 201
    data = saved.json
    path = f"/api/experiments/{data['id']}"
    assert data["experiment"]["results"]["metrics"]["makespan"] == 7
    assert data["owner_id"] == alice.get("/api/session").json["user"]["id"]
    assert len(alice.get("/api/experiments").json["experiments"]) == 1
    assert bob.get("/api/experiments").json == {"experiments": []}
    assert bob.get(path).status_code == 404
    assert bob.patch(path, json={"name": "Stolen"}, headers=bob_headers).status_code == 404
    assert bob.delete(path, headers=bob_headers).status_code == 404
    original_bytes = app.extensions["event_store"].path.read_bytes()
    assert alice.patch(path, json={"name": "Renamed"}, headers=alice_headers).status_code == 200
    assert alice.get(path).json["name"] == "Renamed"
    assert app.extensions["event_store"].path.read_bytes().startswith(original_bytes)
    # A new app instance reads the same disk without in-memory users/results.
    restarted = create_app({"TESTING": True, "SECRET_KEY": "test-secret-key", "STORAGE_PATH": app.config["STORAGE_PATH"]})
    fresh_client = APIClient(restarted.test_client(use_cookies=False))
    login = fresh_client.post("/api/login", json={"username": "alice", "password": "password123"}, headers=token(fresh_client))
    assert login.status_code == 200
    restored = fresh_client.get(path).json
    assert restored["name"] == "Renamed"
    assert restored["configuration"] == CONFIG
    assert restored["experiment"] == data["experiment"]
    before_delete = app.extensions["event_store"].path.read_bytes()
    assert alice.delete(path, headers=alice_headers).status_code == 200
    assert alice.get(path).status_code == 404
    assert fresh_client.get("/api/experiments").json == {"experiments": []}
    assert app.extensions["event_store"].path.read_bytes().startswith(before_delete)
    events = [json.loads(line)["event"] for line in app.extensions["event_store"].path.read_text().splitlines()]
    assert events == ["user_created", "user_created", "experiment_created", "experiment_renamed", "experiment_deleted"]


@pytest.mark.parametrize("name", ["", " ", "x" * 81, None, "bad\nname"])
def test_invalid_saved_names(app, name):
    client = app.test_client()
    headers = account(client)
    assert client.post("/api/experiments", json={"name": name, "configuration": CONFIG}, headers=headers).status_code == 400


@pytest.mark.parametrize("username,password", [("ab", "password123"), ("spaces here", "password123"), ("alice", "short"), ("alice", "x" * 129), (None, "password123")])
def test_invalid_registration(app, username, password):
    client = app.test_client()
    assert client.post("/api/register", json={"username": username, "password": password}, headers=token(client)).status_code == 400


def test_missing_csrf_oversize_payload_and_security_headers(app):
    client = app.test_client()
    assert client.post("/api/simulate", json=CONFIG).status_code == 403
    headers = token(client)
    assert client.post("/api/simulate", json=CONFIG, headers={"X-CSRF-Token": "é"}).status_code == 403
    assert client.post("/api/register", json={"username": "alice", "password": "x" * 40000}, headers=headers).status_code == 413
    result = client.get("/api/session")
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in result.headers["Content-Security-Policy"]
    page = client.get("/")
    assert page.status_code == 404
    assert client.get("/static/app.js").status_code == 404


def test_login_rate_limit(app):
    client = app.test_client()
    headers = token(client)
    for _ in range(10):
        assert client.post("/api/login", json={"username": "alice", "password": "incorrect"}, headers=headers).status_code == 401
    limited = client.post("/api/login", json={"username": "alice", "password": "incorrect"}, headers=headers)
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "900"


def test_limiter_expiration_and_shared_ip_limit():
    now = [1000]
    limiter = AuthLimiter(clock=lambda: now[0])
    for index in range(20):
        assert limiter.allow("127.0.0.1", f"user{index}")
    assert not limiter.allow("127.0.0.1", "different")
    now[0] += 900
    assert limiter.allow("127.0.0.1", "different")


def test_production_config_and_https(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv("STORAGE_PATH", "relative.jsonl")
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "production.jsonl"))
    monkeypatch.setenv("FRONTEND_ORIGINS", "https://fletcherzzk.github.io")
    production = create_app({"TESTING": True})
    client = production.test_client()
    assert client.get("/api/session").status_code == 400
    assert client.get("/api/health").status_code == 200
    session = client.get("/api/session", base_url="https://localhost")
    assert session.status_code == 200
    assert "Set-Cookie" not in session.headers and session.headers["X-Session-Token"]
    assert "max-age=31536000" == session.headers["Strict-Transport-Security"]
    assert client.get("/api/session", headers={"X-Forwarded-Proto": "https"}).status_code == 200


def test_cors_preflight_and_session_headers(app):
    client = app.test_client()
    preflight = client.options("/api/experiments", headers={
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization, content-type, x-csrf-token",
    })
    assert preflight.status_code == 204
    assert preflight.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8000"
    assert "Authorization" in preflight.headers["Access-Control-Allow-Headers"]
    assert "DELETE" in preflight.headers["Access-Control-Allow-Methods"]
    assert "X-Session-Token" not in preflight.headers
    assert "Access-Control-Allow-Credentials" not in preflight.headers
    response = client.get("/api/session")
    assert "X-Session-Token" in response.headers["Access-Control-Expose-Headers"]
    assert "Origin" in response.headers["Vary"]
    assert response.headers["X-Session-Token"]
    assert "Set-Cookie" not in response.headers
    assert client.options("/api/session", headers={"Access-Control-Request-Method": "POST"}).status_code == 405
    assert client.options("/api/session", headers={"Access-Control-Request-Headers": "x-unsafe"}).status_code == 403


def test_disallowed_origin_rejected_before_account_mutation(app):
    client = app.test_client()
    headers = token(client)
    denied = client.post("/api/register", json={"username": "alice", "password": "password123"},
                         headers={**headers, "Origin": "https://untrusted.example"})
    assert denied.status_code == 403
    assert "Access-Control-Allow-Origin" not in denied.headers
    assert "X-Session-Token" not in denied.headers
    assert not app.extensions["event_store"].path.exists()
    denied_preflight = client.options("/api/register", headers={"Origin": "null", "Access-Control-Request-Method": "POST"})
    assert denied_preflight.status_code == 403
    assert "Access-Control-Allow-Origin" not in denied_preflight.headers


def test_bearer_session_tampering_expiry_and_cookie_independence(app):
    from datetime import timedelta
    client = app.test_client()
    account(client)
    saved_token = client.session_token
    client.session_token = saved_token + "corrupted"
    assert client.get("/api/experiments").status_code == 401
    assert client.get("/api/session").json["user"] is None
    client.session_token = saved_token
    assert client.get("/api/session").json["user"]["username"] == "alice"
    client.session_token = saved_token
    app.permanent_session_lifetime = timedelta(seconds=-1)
    assert client.get("/api/experiments").status_code == 401
    assert client.get("/api/session").json["user"] is None


@pytest.mark.parametrize("origins", ["", "*", "null", "https://example.com/path", "https://example.com/", "https://user:pass@example.com", "https://example.com:bad"])
def test_invalid_origin_configuration(tmp_path, origins):
    with pytest.raises(RuntimeError):
        create_app({"FRONTEND_ORIGINS": origins, "STORAGE_PATH": str(tmp_path / "records.jsonl")})
