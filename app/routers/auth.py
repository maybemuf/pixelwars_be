import logging
import secrets

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.core import SESSION_COOKIE, settings
from app.core.telemetry import auth_counter
from app.deps.redis import RedisDep
from app.schemas import ErrorResponse, LogoutResponse, User

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


@router.post(
    "/google",
    status_code=307,
    response_class=RedirectResponse,
    summary="Start the Google login",
    responses={307: {"description": "Redirect to Google's consent screen."}},
)
async def login_via_google(request: Request):
    redirect_uri = request.url_for("authorize_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/google/callback",
    status_code=307,
    response_class=RedirectResponse,
    summary="Google OAuth callback",
    responses={
        307: {"description": "Login succeeded; session cookie set, redirecting to the frontend."},
        401: {"model": ErrorResponse, "description": "Google rejected the exchange, or returned no usable profile."},
    },
)
async def authorize_google(
    request: Request,
    redis: RedisDep,
) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("google oauth exchange failed: %s", exc)
        auth_counter.add(1, {"provider": "google", "result": "failed"})
        raise HTTPException(status_code=401, detail="Google auth failed") from exc

    try:
        user = User.model_validate(token.get("userinfo"))
    except ValidationError as exc:
        # A token without usable userinfo is a failed login, not a server fault; this
        # used to escape as a 500.
        logger.warning("google returned no usable userinfo")
        auth_counter.add(1, {"provider": "google", "result": "failed"})
        raise HTTPException(status_code=401, detail="Google auth failed") from exc

    session_id = secrets.token_urlsafe(32)
    await redis.set(f"session:{session_id}", user.model_dump_json(), ex=settings.SESSION_TTL)

    logger.info("session created for user %s", user.id)

    response = RedirectResponse(str(settings.FRONTEND_URL))
    response.set_cookie("session", session_id, max_age=settings.SESSION_TTL, **SESSION_COOKIE)
    auth_counter.add(1, {"provider": "google", "result": "success"})
    return response


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out",
    responses={200: {"description": "Session destroyed. Idempotent: succeeds with no session too."}},
)
async def logout_user(
    response: Response,
    redis: RedisDep,
    session: str | None = Cookie(default=None),
) -> LogoutResponse:
    if session:
        await redis.delete(f"session:{session}")
    logger.info("logout requested: session_present=%s", session is not None)
    response.delete_cookie("session", **SESSION_COOKIE)
    return LogoutResponse(ok=True)
