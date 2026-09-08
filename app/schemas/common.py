from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str = Field(description='"ok", or "unavailable" when a dependency is down.', examples=["ok"])
    redis: str | None = Field(
        default=None,
        description='"up" or "down". Absent from the liveness probe, which takes no dependencies.',
        examples=["up"],
    )


class LogoutResponse(BaseModel):
    ok: bool = Field(description="Always true; logout is idempotent and succeeds without a session.")


class ErrorResponse(BaseModel):
    detail: str = Field(examples=["Not authenticated"])
