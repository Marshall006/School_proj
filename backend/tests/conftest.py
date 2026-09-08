"""Socle de tests : base en memoire, client HTTP, foyer de demonstration."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

# Doit preceder tout import de l'application : la configuration est un singleton.
os.environ.setdefault("KODA_ENVIRONMENT", "test")
os.environ.setdefault("KODA_DEBUG", "false")
os.environ.setdefault("KODA_SEED_ON_STARTUP", "false")
os.environ.setdefault("KODA_SECRET_KEY", "cle-de-test-tres-longue-et-stable-0123456789")
os.environ.setdefault("KODA_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("KODA_PBKDF2_ITERATIONS", "1000")  # tests rapides
os.environ.setdefault("KODA_RATE_LIMIT_PER_MINUTE", "100000")

from datetime import timedelta  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.content.seed import seed_all  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

#: Contenu reduit : la France, deux niveaux. Suffisant et rapide.
TEST_COUNTRIES = ("FR",)
TEST_LEVELS = (4, 5)


@pytest.fixture(autouse=True)
def heure_ouvree():
    """Cale l'horloge applicative sur 15 h a Paris pendant toute la suite.

    Sans cela, une suite lancee a 3 h du matin echouerait sur le couvre-feu :
    un test ne doit jamais dependre de l'heure a laquelle on le lance.
    """
    from app.core import clock

    local = clock.now().astimezone(ZoneInfo("Europe/Paris"))
    delta = timedelta(hours=15 - local.hour, minutes=-local.minute, seconds=-local.second)
    with clock.time_travel(delta):
        yield


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker_(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def db(sessionmaker_) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker_() as session:
        yield session


@pytest.fixture
async def content(db) -> dict[str, int]:
    """Banque pedagogique reduite, partagee par les tests qui en ont besoin."""
    return await seed_all(db, countries=TEST_COUNTRIES, levels=TEST_LEVELS)


@pytest.fixture
async def client(sessionmaker_) -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker_() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fabriques de scenario
# ---------------------------------------------------------------------------


class Api:
    """Petit client de haut niveau : evite de repeter les en-tetes dans les tests."""

    def __init__(self, http: AsyncClient) -> None:
        self.http = http
        self.parent_token: str | None = None
        self.device_token: str | None = None
        self.prefix = "/api/v1"

    def _headers(self, as_device: bool = False) -> dict[str, str]:
        token = self.device_token if as_device else self.parent_token
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def post(self, path: str, json: Any = None, *, as_device: bool = False, **kw):
        return await self.http.post(
            self.prefix + path, json=json, headers=self._headers(as_device), **kw
        )

    async def get(self, path: str, *, as_device: bool = False, **kw):
        return await self.http.get(self.prefix + path, headers=self._headers(as_device), **kw)

    async def patch(self, path: str, json: Any = None, *, as_device: bool = False, **kw):
        return await self.http.patch(
            self.prefix + path, json=json, headers=self._headers(as_device), **kw
        )

    async def put(self, path: str, json: Any = None, *, as_device: bool = False, **kw):
        return await self.http.put(
            self.prefix + path, json=json, headers=self._headers(as_device), **kw
        )

    async def delete(self, path: str, *, as_device: bool = False, **kw):
        return await self.http.delete(self.prefix + path, headers=self._headers(as_device), **kw)


@pytest.fixture
async def api(client) -> Api:
    return Api(client)


@pytest.fixture
async def parent(api: Api) -> dict[str, Any]:
    """Foyer inscrit, jeton parent pret a l'emploi."""
    response = await api.post(
        "/auth/register",
        {
            "email": f"parent-{uuid.uuid4().hex[:8]}@example.com",
            "password": "motdepasse-solide-1",
            "display_name": "Amina",
            "family_name": "Foyer Test",
            "country_code": "FR",
            "timezone": "Europe/Paris",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    api.parent_token = data["tokens"]["access_token"]
    return data


@pytest.fixture
async def child(api: Api, parent, content) -> dict[str, Any]:
    response = await api.post(
        "/children",
        {"display_name": "Noam", "grade_code": "CM1", "country_code": "FR", "avatar": "fox"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def device(api: Api, child) -> dict[str, Any]:
    """Appareil appaire : renvoie les identifiants dont `device_secret`."""
    pairing = await api.post(
        "/devices/pairing-code", {"child_id": child["id"], "suggested_name": "Tablette de Noam"}
    )
    assert pairing.status_code == 201, pairing.text
    claim = await api.post(
        "/devices/claim",
        {
            "pairing_code": pairing.json()["code"],
            "name": "Tablette de Noam",
            "platform": "android",
            "app_version": "1.0.0",
            "boot_id": "boot-1",
        },
    )
    assert claim.status_code == 201, claim.text
    credentials = claim.json()
    api.device_token = credentials["device_token"]
    return credentials
