"""Configuration centralisee de l'API KODA.

Toutes les valeurs sont surchargeables par variables d'environnement
(prefixe KODA_) ou par un fichier .env.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KODA_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identite ---------------------------------------------------------
    app_name: str = "KODA"
    app_tagline: str = "L'écran se mérite."
    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # --- Base de donnees --------------------------------------------------
    # Par defaut SQLite, dans le dossier depuis lequel on lance la commande :
    # le projet demarre sans aucune infrastructure. La production passe a
    # PostgreSQL via KODA_DATABASE_URL (docker-compose le fait deja).
    database_url: str = "sqlite+aiosqlite:///./koda.db"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Securite ---------------------------------------------------------
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 30
    device_token_ttl_days: int = 3650  # un appareil apparie reste apparie
    pbkdf2_iterations: int = 240_000

    # --- Firebase (optionnel : si non configure, auth locale uniquement) ---
    firebase_project_id: str | None = None
    firebase_certs_url: str = (
        "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
    )

    # --- Protocole de deverrouillage --------------------------------------
    unlock_code_digits: int = 9
    unlock_tag_digits: int = 6
    unlock_lookahead_window: int = 32
    unlock_code_ttl_minutes: int = 30
    unlock_max_failed_attempts: int = 5
    unlock_lockout_seconds: int = 300

    # --- Moteur de temps d'ecran ------------------------------------------
    heartbeat_interval_seconds: int = 30
    heartbeat_grace_factor: float = 2.5
    session_wall_stretch_factor: float = 3.0  # anti-abus de la mise en pause
    max_clock_skew_ms: int = 120_000

    # --- Regles pedagogiques par defaut -----------------------------------
    default_pass_score_pct: float = 70.0  # 14/20
    default_cooldown_minutes: int = 120
    default_reward_minutes: int = 180
    default_question_count: int = 10
    default_daily_cap_minutes: int = 300
    default_max_attempts_per_day: int = 4
    default_minutes_per_100_xp: int = 15
    default_xp_daily_bonus_cap_minutes: int = 60

    # --- Divers -----------------------------------------------------------
    # `NoDecode` desactive le decodage JSON automatique : sans cela,
    # KODA_CORS_ORIGINS="http://a,http://b" leverait une erreur au demarrage.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    rate_limit_per_minute: int = 240
    seed_on_startup: bool = True
    server_timezone: str = "Europe/Paris"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accepte aussi bien une liste JSON qu'une simple liste separee par des virgules."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                return json.loads(text)
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
