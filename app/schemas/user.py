from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    id: str = Field(validation_alias="sub")
    name: str = Field(validation_alias="name")
    email: EmailStr
    avatar_url: str = Field(validation_alias="picture")
