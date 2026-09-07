import logging
import secrets

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.core import settings
from app.core.telemetry import auth_counter
from app.deps.redis import RedisDep
from app.schemas import User

oauth = OAuth()
oauth.register(
    "google",
    client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
    client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google")
async def login_via_google(request: Request):
    redirect_uri = request.url_for("authorize_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def authorize_google(
    request: Request,
    redis: RedisDep,
) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        # The client only ever sees a flat 401; without this the reason (bad redirect_uri,
        # expired state, clock skew) is lost entirely.
        logger.warning("google oauth exchange failed: %s", exc)
        auth_counter.add(1, {"provider": "google", "result": "failed"})
        raise HTTPException(status_code=401, detail="Google auth failed") from exc

    user = User.model_validate(token.get("userinfo"))

    session_id = secrets.token_urlsafe(32)
    await redis.set(f"session:{session_id}", user.model_dump_json(), settings.SESSION_TTL)

    # Auth events are the audit trail. user.id (Google `sub`) identifies the account;
    # session_id must never be logged — it is a bearer credential.
    logger.info("session created for user %s", user.id)

    response = RedirectResponse(settings.FRONTEND_URL)
    response.set_cookie(
        "session",
        session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.SESSION_TTL,
    )
    auth_counter.add(1, {"provider": "google", "result": "success"})
    return response


@router.post("/logout")
async def logout_user(
    response: Response,
    redis: RedisDep,
    session: str | None = Cookie(default=None),
):
    if session:
        await redis.delete(f"session:{session}")
    logger.info("logout requested: session_present=%s", session is not None)
    response.delete_cookie(
        "session",
        httponly=True,
        secure=True,
        samesite="none",
    )
    return {"ok": True}
