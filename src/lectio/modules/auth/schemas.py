from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from lectio.models.enums import UserRole
from lectio.modules.users.schemas import Name, UserResponse


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    first_name: Name
    last_name: Name
    role: UserRole = UserRole.STUDENT


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class AuthResponse(AccessTokenResponse):
    user: UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
