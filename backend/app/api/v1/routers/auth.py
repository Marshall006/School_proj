"""Inscription, connexion, rafraichissement de session."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
from fastapi import APIRouter, Header
from sqlalchemy import select

from app.api.deps import CurrentParent, DbSession
from app.core.clock import now as clock_now
from app.core.config import settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_token,
    decode_token,
    hash_opaque,
    hash_password,
    verify_password,
)
from app.models.enums import ParentRole
from app.models.family import Family, Parent, RefreshToken
from app.schemas.auth import (
    FamilyOut,
    FirebaseLoginRequest,
    LoginRequest,
    ParentOut,
    RefreshRequest,
    RegisterRequest,
    SessionOut,
    TokenPair,
)
from app.services import audit, firebase

router = APIRouter(prefix="/auth", tags=["Authentification"])


async def _issue_tokens(db: DbSession, parent: Parent, user_agent: str | None = None) -> TokenPair:
    access = create_token(
        str(parent.id),
        "access",
        claims={"family_id": str(parent.family_id), "role": parent.role.value},
    )
    refresh_raw = create_token(str(parent.id), "refresh")
    db.add(
        RefreshToken(
            parent_id=parent.id,
            token_hash=hash_opaque(refresh_raw),
            expires_at=clock_now() + timedelta(days=settings.refresh_token_ttl_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh_raw,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.post("/register", response_model=SessionOut, status_code=201)
async def register(
    db: DbSession,
    payload: RegisterRequest,
    user_agent: str | None = Header(default=None),
) -> SessionOut:
    """Cree un foyer et son premier parent (proprietaire)."""
    existing = (
        await db.execute(select(Parent).where(Parent.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Un compte existe déjà avec cette adresse.", code="email_taken")

    family = Family(
        name=payload.family_name,
        country_code=payload.country_code,
        timezone=payload.timezone,
    )
    db.add(family)
    await db.flush()

    parent = Parent(
        family_id=family.id,
        email=payload.email.lower(),
        phone=payload.phone,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=ParentRole.OWNER,
        last_login_at=clock_now(),
    )
    db.add(parent)
    await db.flush()

    tokens = await _issue_tokens(db, parent, user_agent)
    await audit.record(
        db,
        family_id=family.id,
        action="parent.registered",
        actor_type="parent",
        actor_id=parent.id,
        payload={"email": parent.email},
    )
    await db.commit()
    return SessionOut(
        parent=ParentOut.model_validate(parent),
        family=FamilyOut.model_validate(family),
        tokens=tokens,
    )


@router.post("/login", response_model=SessionOut)
async def login(
    db: DbSession,
    payload: LoginRequest,
    user_agent: str | None = Header(default=None),
) -> SessionOut:
    parent = (
        await db.execute(select(Parent).where(Parent.email == payload.email.lower()))
    ).scalar_one_or_none()
    if parent is None or not parent.password_hash:
        raise AuthenticationError("Adresse ou mot de passe incorrect.")
    if not verify_password(payload.password, parent.password_hash):
        raise AuthenticationError("Adresse ou mot de passe incorrect.")
    if not parent.is_active:
        raise AuthenticationError("Ce compte est desactive.")

    parent.last_login_at = clock_now()
    tokens = await _issue_tokens(db, parent, user_agent)
    family = await db.get(Family, parent.family_id)
    await db.commit()
    return SessionOut(
        parent=ParentOut.model_validate(parent),
        family=FamilyOut.model_validate(family),
        tokens=tokens,
    )


@router.post("/firebase", response_model=SessionOut)
async def firebase_login(
    db: DbSession,
    payload: FirebaseLoginRequest,
    user_agent: str | None = Header(default=None),
) -> SessionOut:
    """Echange un jeton Firebase (telephone / e-mail) contre une session KODA."""
    claims = await firebase.verify_id_token(payload.id_token)
    uid = claims.get("sub") or claims.get("user_id")
    email = (claims.get("email") or f"{uid}@firebase.local").lower()
    phone = claims.get("phone_number")

    parent = (
        await db.execute(select(Parent).where(Parent.firebase_uid == uid))
    ).scalar_one_or_none()
    if parent is None:
        parent = (
            await db.execute(select(Parent).where(Parent.email == email))
        ).scalar_one_or_none()

    if parent is None:
        family = Family(
            name=payload.family_name or f"Foyer de {payload.display_name or 'la famille'}",
            country_code=payload.country_code.upper(),
        )
        db.add(family)
        await db.flush()
        parent = Parent(
            family_id=family.id,
            email=email,
            phone=phone,
            display_name=payload.display_name or claims.get("name") or "Parent",
            firebase_uid=uid,
            role=ParentRole.OWNER,
        )
        db.add(parent)
        await db.flush()
    else:
        parent.firebase_uid = uid
        if phone and not parent.phone:
            parent.phone = phone

    parent.last_login_at = clock_now()
    tokens = await _issue_tokens(db, parent, user_agent)
    family = await db.get(Family, parent.family_id)
    await db.commit()
    return SessionOut(
        parent=ParentOut.model_validate(parent),
        family=FamilyOut.model_validate(family),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(db: DbSession, payload: RefreshRequest) -> TokenPair:
    """Rotation stricte : un jeton de rafraichissement ne sert qu'une fois."""
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Jeton de rafraichissement invalide.") from exc

    stored = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_opaque(payload.refresh_token)
            )
        )
    ).scalar_one_or_none()
    if stored is None or stored.revoked_at is not None or stored.expires_at < clock_now():
        raise AuthenticationError("Session expiree, reconnecte-toi.", code="refresh_expired")

    parent = await db.get(Parent, uuid.UUID(claims["sub"]))
    if parent is None or not parent.is_active:
        raise AuthenticationError("Compte introuvable.")

    stored.revoked_at = clock_now()
    tokens = await _issue_tokens(db, parent, stored.user_agent)
    await db.flush()
    new_row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_opaque(tokens.refresh_token))
        )
    ).scalar_one()
    stored.replaced_by = new_row.id
    await db.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(db: DbSession, payload: RefreshRequest) -> None:
    stored = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_opaque(payload.refresh_token)
            )
        )
    ).scalar_one_or_none()
    if stored is not None:
        stored.revoked_at = clock_now()
        await db.commit()


@router.get("/me", response_model=SessionOut)
async def me(db: DbSession, parent: CurrentParent) -> SessionOut:
    family = await db.get(Family, parent.family_id)
    return SessionOut(
        parent=ParentOut.model_validate(parent),
        family=FamilyOut.model_validate(family),
        tokens=TokenPair(access_token="", refresh_token="", expires_in=0),
    )
