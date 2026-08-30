import secrets

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.core import settings
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
        raise HTTPException(status_code=401, detail="Google auth failed") from exc

    user = User.model_validate(token.get("userinfo"))

    session_id = secrets.token_urlsafe(32)
    await redis.set(f"session:{session_id}", user.model_dump_json(), settings.SESSION_TTL)

    response = RedirectResponse(settings.FRONTEND_URL)
    response.set_cookie(
        "session",
        session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.SESSION_TTL,
    )

    return response


@router.post("/logout")
async def logout_user(
    response: Response,
    redis: RedisDep,
    session: str | None = Cookie(default=None),
):
    if session:
        await redis.delete(f"session:{session}")
    response.delete_cookie(
        "session",
        httponly=True,
        secure=True,
        samesite="none",
    )
    return {"ok": True}
