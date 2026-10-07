"""Flask signed sessions transported as bearer tokens instead of cookies.

Pages and Render are cross-site: cookie sessions depend on third-party-cookie
permission. This interface reuses Flask/itsdangerous signing and expiry while
letting the static frontend retain the session in per-tab sessionStorage.
"""

import hashlib

from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature


class HeaderSessionInterface(SecureCookieSessionInterface):
    salt = "parallel-lab-api-session-v1"
    digest_method = staticmethod(hashlib.sha256)

    def open_session(self, app, request):
        serializer = self.get_signing_serializer(app)
        if serializer is None:
            return None
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return self.session_class()
        token = authorization[7:]
        if not token or len(token) > 4096:
            return self.session_class()
        try:
            data = serializer.loads(token, max_age=int(app.permanent_session_lifetime.total_seconds()))
            if not isinstance(data, dict):
                return self.session_class()
            return self.session_class(data)
        except BadSignature:
            return self.session_class()

    def save_session(self, app, session, response):
        # Preflights and rejected origins never create/refresh credentials.
        from flask import request
        if (not request.path.startswith("/api/") or request.method == "OPTIONS"
                or request.headers.get("Origin") not in (None, *app.config["FRONTEND_ORIGINS"])):
            return
        serializer = self.get_signing_serializer(app)
        if serializer is not None:
            response.headers["X-Session-Token"] = serializer.dumps(dict(session)) if session else ""
        # Deliberately no Set-Cookie: the browser sends credentials explicitly.
