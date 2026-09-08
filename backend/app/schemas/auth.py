"""Inscription, connexion, jetons."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    country_code: str = Field(default="FR", min_length=2, max_length=2)
    timezone: str = "Europe/Paris"

    @field_validator("country_code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FirebaseLoginRequest(BaseModel):
    id_token: str
    display_name: str | None = None
    family_name: str | None = None
    country_code: str = "FR"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ParentOut(ORMModel):
    id: uuid.UUID
    family_id: uuid.UUID
    email: str
    display_name: str
    phone: str | None = None
    role: str
    created_at: datetime


class FamilyOut(ORMModel):
    id: uuid.UUID
    name: str
    country_code: str
    timezone: str
    locale: str


class SessionOut(BaseModel):
    parent: ParentOut
    family: FamilyOut
    tokens: TokenPair
