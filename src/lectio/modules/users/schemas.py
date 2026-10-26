from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)

from lectio.models.enums import UserRole

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class PublicUserResponse(BaseModel):
    """What anyone may see about a user, e.g. a lecture's instructor."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    role: UserRole

    avatar_path: str | None = Field(
        default=None,
        exclude=True,
    )

    @computed_field
    @property
    def avatar_url(self) -> str | None:
        if self.avatar_path is None:
            return None

        return f"/api/v1/users/{self.id}/avatar"


class UserResponse(PublicUserResponse):
    email: EmailStr
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None

    @field_validator(
        "first_name",
        "last_name",
    )
    @classmethod
    def names_cannot_be_null(
        cls,
        value: str | None,
    ) -> str:
        if value is None:
            raise ValueError("Name cannot be null")

        return value
