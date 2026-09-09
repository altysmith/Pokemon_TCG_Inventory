"""Verified Cloudflare identity and request-local collection storage."""

from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import hashlib
import os
import re


class AuthenticationError(ValueError):
    pass


class AccessIdentity:
    def __init__(self, issuer, audience):
        import jwt

        if (
            not re.fullmatch(r"https://[a-z0-9-]+\.cloudflareaccess\.com", issuer)
            or not audience
        ):
            raise ValueError("Hosted mode requires a Cloudflare issuer and audience.")
        self.issuer = issuer
        self.audience = audience
        self.keys = jwt.PyJWKClient(issuer + "/cdn-cgi/access/certs", timeout=5)

    def verify(self, token):
        import jwt

        if not token or len(token) > 32768:
            raise AuthenticationError("Sign in to access your collection.")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]},
            )
            if claims.get("type") != "app":
                raise AuthenticationError("An application login is required.")
            return normalize_email(claims["email"])
        except (jwt.PyJWTError, OSError, ValueError) as exc:
            raise AuthenticationError("Sign in to access your collection.") from exc


def normalize_email(email):
    if (
        not isinstance(email, str)
        or not re.fullmatch(r"[^\s@]+@[^\s@]+", email.strip())
        or len(email) > 254
    ):
        raise AuthenticationError("A verified email address is required.")
    return email.strip().casefold()


def tenant_id(email):
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


HOSTED = os.environ.get("COLLECTION_HOSTED", "0") == "1"
USERS_ROOT = Path(
    os.environ.get(
        "COLLECTION_USERS_ROOT",
        Path(__file__).resolve().parent / "user_data" / "users",
    )
)
PUBLIC_ORIGIN = os.environ.get("COLLECTION_PUBLIC_ORIGIN", "").rstrip("/")
IDENTITY = (
    AccessIdentity(
        os.environ.get("CF_ACCESS_ISSUER", ""),
        os.environ.get("CF_ACCESS_AUDIENCE", ""),
    )
    if HOSTED
    else None
)
if HOSTED and not re.fullmatch(r"https://[a-z0-9.-]+", PUBLIC_ORIGIN):
    raise ValueError("Hosted mode requires an HTTPS public origin.")
CURRENT_EMAIL = ContextVar("collection_email", default=None)


def scoped_path(relative, local_path):
    if not HOSTED:
        return local_path
    email = CURRENT_EMAIL.get()
    if email is None:
        raise AuthenticationError("No verified collection owner in this request.")
    return USERS_ROOT / tenant_id(email) / relative


def authenticated(method):
    @wraps(method)
    def dispatch(handler):
        context = CURRENT_EMAIL.set(None)
        try:
            if HOSTED:
                # Health is deliberately anonymous and contains no collection data.
                if handler.command == "GET" and handler.path.split("?", 1)[0] == "/health":
                    handler._json({"ok": True, "multi_user": True})
                    return
                try:
                    email = IDENTITY.verify(
                        handler.headers.get("Cf-Access-Jwt-Assertion", "")
                    )
                except AuthenticationError:
                    handler.close_connection = True
                    handler._json(
                        {"ok": False, "error": "Sign in to access your collection."},
                        401,
                    )
                    return
                CURRENT_EMAIL.set(email)
                if handler.path.startswith("/desktop-session/"):
                    handler.close_connection = True
                    handler._json(
                        {"ok": False, "error": "Not available on the hosted app."},
                        404,
                    )
                    return
                if handler.command == "POST":
                    origin = handler.headers.get("Origin")
                    content_type = (
                        handler.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if (
                        (origin is not None and origin != PUBLIC_ORIGIN)
                        or handler.headers.get("Sec-Fetch-Site") == "cross-site"
                        or content_type != "application/json"
                    ):
                        handler.close_connection = True
                        handler._json(
                            {
                                "ok": False,
                                "error": "Request must come from this collection app.",
                            },
                            403,
                        )
                        return
            return method(handler)
        finally:
            CURRENT_EMAIL.reset(context)

    return dispatch
