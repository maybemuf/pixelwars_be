from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request

from app.core import settings

oauth = OAuth()
oauth.register(
    'google',
    client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
    client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration"
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.get("/google")
async def login_via_google(request: Request):
    redirect_uri = request.url_for("authorize_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def authorize_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")   
    return dict(user)
