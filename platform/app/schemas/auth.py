from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    user_id: int
    email: EmailStr
    full_name: str
    provider: str
    picture: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field("", max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google ID token JWT from the GIS button")
