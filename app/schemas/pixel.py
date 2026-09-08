from dataclasses import dataclass
from enum import StrEnum

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field

from app.core import BOARD_KEY, BOARD_MAX_OFFSET


def snake_to_dotted(name: str) -> str:
    return name.replace("_", ".")


class PixelPlacement(BaseModel):
    offset: int = Field(ge=0, le=BOARD_MAX_OFFSET)
    color: int = Field(le=15, ge=0)


@dataclass
class PixelPlacementResult:
    board_id: str
    retry_in_ms: int


@dataclass
class PixelPlacementSuccess(PixelPlacementResult):
    entry_id: str
    pixels_placed: int


@dataclass
class PixelPlacementError(PixelPlacementResult):
    pass


class PixelResultEnum(StrEnum):
    ACCEPTED = "accepted"
    COOLDOWN = "cooldown"
    INVALID = "invalid"
    UNAUTHENTICATED = "unauthenticated"


class SetPixelSpanAttributes(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(serialization_alias=snake_to_dotted),
        populate_by_name=True,
        serialize_by_alias=True,
    )
    board_id: str = BOARD_KEY
    pixel_offset: int | None = None
    pixel_color: int | None = None
    pixel_result: PixelResultEnum
    cooldown_retry_in_ms: int | None = None
    enduser_id: str | None = None
    stream_entry_id: str | None = None
