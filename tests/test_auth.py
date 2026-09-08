"""The Google OAuth flow. Authlib is patched at oauth.google, which also keeps the
OIDC discovery fetch off the network."""

import asyncio

import pytest
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse

from app.core import settings
from app.routers import auth as sut

USERINFO = {"sub": "g-123", "name": "Lesha", "email": "a@b.co", "picture": "http://x/p.png"}


@pytest.fixture
def google(monkeypatch):
    """Stands in for oauth.google, recording what the router handed it."""

    class FakeGoogle:
        def __init__(self):
            self.redirect_uri = None
            self.token = {"userinfo": USERINFO}
            self.error = None

        async def authorize_redirect(self, request, redirect_uri=None, **kw):
            self.redirect_uri = redirect_uri
            return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?x=1")

        async def authorize_access_token(self, request, **kw):
            if self.error:
                raise self.error
            return self.token

    fake = FakeGoogle()
    monkeypatch.setattr(sut.oauth, "google", fake, raising=False)
    return fake


def test_login_redirects_to_google(client, google):
    r = client.post("/auth/google", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"].startswith("https://accounts.google.com/")
    # Pins request.url_for("authorize_google"): rename the handler and Google starts
    # rejecting the redirect_uri in production.
    assert google.redirect_uri == "https://testserver/auth/google/callback"


def test_callback_creates_session_and_sets_cookie(client, redis, google):
    r = client.get("/auth/google/callback", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == str(settings.FRONTEND_URL)

    # These four flags are the session's entire security contract.
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=none" in cookie
    assert f"Max-Age={settings.SESSION_TTL}" in cookie

    sid = client.cookies["session"]
    stored = asyncio.run(redis.get(f"session:{sid}"))
    # Stored by field name, not by the sub/picture aliases -- which is exactly why
    # get_current_user has to pass by_name=True.
    assert stored == b'{"id":"g-123","name":"Lesha","email":"a@b.co","avatar_url":"http://x/p.png"}'
    # Cookie Max-Age and the Redis TTL must agree, or one outlives the other.
    assert asyncio.run(redis.ttl(f"session:{sid}")) == settings.SESSION_TTL


def test_callback_oauth_error_is_401_and_no_session(client, redis, google):
    google.error = OAuthError(error="access_denied", description="nope")

    r = client.get("/auth/google/callback", follow_redirects=False)

    assert r.status_code == 401
    assert r.json() == {"detail": "Google auth failed"}
    assert "set-cookie" not in r.headers
    # A failed exchange must not mint a session.
    assert asyncio.run(redis.keys("session:*")) == []


def test_callback_without_userinfo_is_401_not_500(client, redis, google):
    """Google omitting userinfo used to escape as a ValidationError -> 500."""
    google.token = {}

    r = client.get("/auth/google/callback", follow_redirects=False)

    assert r.status_code == 401
    assert asyncio.run(redis.keys("session:*")) == []


def test_logout_clears_session(client, redis, session_cookie):
    client.cookies.set("session", session_cookie)

    r = client.post("/auth/logout")

    assert r.json() == {"ok": True}
    assert asyncio.run(redis.get(f"session:{session_cookie}")) is None
    assert "Max-Age=0" in r.headers["set-cookie"]


def test_logout_without_cookie_is_still_ok(client):
    """Guards the `if session:` branch -- no cookie must not be an error."""
    r = client.post("/auth/logout")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
