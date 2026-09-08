"""Outils d'administration en ligne de commande.

python -m app.cli seed          # remplit la banque pedagogique
python -m app.cli demo          # cree le foyer de demonstration
python -m app.cli stats         # etat du contenu
python -m app.cli housekeeping  # expire codes, sessions et epreuves perimes
python -m app.cli verify-audit --family <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from app.content.demo import seed_demo
from app.content.seed import content_stats, seed_all
from app.core.config import settings
from app.db.session import dispose_engine, get_engine, get_sessionmaker
from app.models import Base
from app.services import assessment as assessment_svc
from app.services import audit, screen_time, unlock


async def _ensure_schema() -> None:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def cmd_seed(args: argparse.Namespace) -> dict:
    await _ensure_schema()
    async with get_sessionmaker()() as db:
        countries = tuple(args.countries.split(",")) if args.countries else None
        levels = tuple(int(x) for x in args.levels.split(",")) if args.levels else None
        kwargs = {}
        if countries:
            kwargs["countries"] = countries
        if levels:
            kwargs["levels"] = levels
        return await seed_all(db, **kwargs)


async def cmd_demo(args: argparse.Namespace) -> dict:
    await _ensure_schema()
    async with get_sessionmaker()() as db:
        await seed_all(db)
        return await seed_demo(db, days=args.days)


async def cmd_stats(args: argparse.Namespace) -> dict:
    async with get_sessionmaker()() as db:
        return await content_stats(db)


async def cmd_housekeeping(args: argparse.Namespace) -> dict:
    async with get_sessionmaker()() as db:
        report = {
            "codes_expires": await unlock.expire_stale_codes(db),
            "sessions_expirees": await screen_time.expire_stale_sessions(db),
            "epreuves_expirees": await assessment_svc.expire_stale_assessments(db),
        }
        await db.commit()
        return report


async def cmd_verify_audit(args: argparse.Namespace) -> dict:
    async with get_sessionmaker()() as db:
        return await audit.verify_chain(db, uuid.UUID(args.family))


COMMANDS = {
    "seed": cmd_seed,
    "demo": cmd_demo,
    "stats": cmd_stats,
    "housekeeping": cmd_housekeeping,
    "verify-audit": cmd_verify_audit,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koda", description="Administration KODA")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="remplit la banque pedagogique")
    seed.add_argument("--countries", help="codes pays separes par des virgules (FR,BJ,CI,SN)")
    seed.add_argument("--levels", help="indices de niveau separes par des virgules (2,3,4,5,6)")

    demo = sub.add_parser("demo", help="cree le foyer de demonstration")
    demo.add_argument("--days", type=int, default=21, help="profondeur de l'historique simule")

    sub.add_parser("stats", help="etat de la banque pedagogique")
    sub.add_parser("housekeeping", help="expire codes, sessions et epreuves perimes")

    verify = sub.add_parser("verify-audit", help="revalide la chaine d'audit d'un foyer")
    verify.add_argument("--family", required=True, help="identifiant du foyer")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    async def run() -> None:
        try:
            result = await COMMANDS[args.command](args)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        finally:
            await dispose_engine()

    print(f"Base : {settings.database_url.split('@')[-1]}")
    asyncio.run(run())


if __name__ == "__main__":
    main()
