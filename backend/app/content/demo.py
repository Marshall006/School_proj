"""Jeu de démonstration : un foyer credible, avec trois semaines d'historique.

Sert à deux choses :

- faire vivre le tableau de bord parental des la première minute (sans quoi il
  n'affiche que des zeros) ;
- fournir un scenario de bout en bout rejouable pour les demonstrations.

L'historique est simule en remontant le temps applicatif : les évaluations, les
sessions d'écran et les mouvements d'XP sont produits par les *vrais* services,
pas par des insertions artificielles. Ce que le tableau de bord affiche est donc
exactement ce que produirait un usage reel.
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import unlock_protocol as proto
from app.core.clock import now as clock_now
from app.core.clock import time_travel
from app.core.security import generate_pairing_code, hash_opaque, hash_password, hash_pin
from app.models.content import Question
from app.models.device import Device
from app.models.enums import (
    AnswerMode,
    AssessmentKind,
    DevicePlatform,
    ParentRole,
    PeriodType,
)
from app.models.family import Child, Family, Parent
from app.models.policy import CalendarPeriod, PolicyProfile
from app.services import assessment as assessment_svc
from app.services import screen_time, unlock
from app.services.policy import resolve_policy

logger = logging.getLogger("koda.demo")

DEMO_EMAIL = "demo@koda.app"
DEMO_PASSWORD = "demo-koda-2026"

#: Profil de competence par enfant : probabilite de reussite par matiere.
SKILL_PROFILES: dict[str, dict[str, float]] = {
    "Noam": {
        "math": 0.85,
        "francais": 0.55,
        "sciences": 0.75,
        "histoire_geo": 0.7,
        "anglais": 0.6,
        "civique": 0.8,
    },
    "Aya": {
        "math": 0.5,
        "francais": 0.9,
        "sciences": 0.8,
        "histoire_geo": 0.85,
        "anglais": 0.75,
        "civique": 0.85,
    },
}


def _answer_for(question: Question, correct: bool, rng: random.Random) -> dict[str, Any]:
    """Fabrique une réponse juste ou fausse à partir du bareme."""
    spec = question.answer or {}
    qtype = question.type.value
    if correct:
        match qtype:
            case "mcq_single":
                return {"choice": spec["correct"][0]}
            case "mcq_multi":
                return {"choices": list(spec["correct"])}
            case "true_false":
                return {"value": spec["correct"]}
            case "short_text":
                return {"value": spec["accept"][0]}
            case "fill_blank":
                return {"values": [b["accept"][0] for b in spec["blanks"]]}
            case "ordering":
                return {"order": list(spec["order"])}
            case "matching":
                return {"pairs": dict(spec["pairs"])}
            case "handwritten":
                return {"transcript": str(spec.get("value")), "has_strokes": True}
            case _:
                return {"value": spec.get("value")}
    match qtype:
        case "mcq_single" | "mcq_multi":
            choices = [c["id"] for c in (question.choices or [])]
            wrong = [c for c in choices if c not in set(spec.get("correct", []))]
            pick = rng.choice(wrong) if wrong else "z"
            return {"choice": pick} if qtype == "mcq_single" else {"choices": [pick]}
        case "true_false":
            return {"value": not spec["correct"]}
        case "short_text":
            return {"value": "je ne sais pas"}
        case "fill_blank":
            return {"values": ["???" for _ in spec["blanks"]]}
        case "ordering":
            return {"order": list(reversed(spec["order"]))}
        case "matching":
            return {"pairs": dict.fromkeys(spec["pairs"], "???")}
        case "handwritten":
            return {"transcript": "", "has_strokes": True}
        case _:
            return {"value": -1}


async def seed_demo(db: AsyncSession, *, days: int = 21, seed: int = 20260315) -> dict[str, Any]:
    """Créé (ou retrouve) le foyer de démonstration et son historique."""
    existing = (
        await db.execute(select(Parent).where(Parent.email == DEMO_EMAIL))
    ).scalar_one_or_none()
    if existing is not None:
        return {"created": False, "email": DEMO_EMAIL, "family_id": str(existing.family_id)}

    rng = random.Random(seed)
    today = clock_now().date()

    family = Family(name="Famille Diallo", country_code="FR", timezone="Europe/Paris")
    db.add(family)
    await db.flush()

    parent = Parent(
        family_id=family.id,
        email=DEMO_EMAIL,
        phone="+33600000000",
        display_name="Amina Diallo",
        password_hash=hash_password(DEMO_PASSWORD),
        role=ParentRole.OWNER,
    )
    db.add(parent)

    children: list[Child] = []
    for name, grade, avatar, pin in (
        ("Noam", "CM1", "fox", "1234"),
        ("Aya", "CM2", "owl", "4321"),
    ):
        child = Child(
            family_id=family.id,
            display_name=name,
            grade_code=grade,
            country_code="FR",
            avatar=avatar,
            pin_hash=hash_pin(pin),
            birth_date=date(today.year - (10 if grade == "CM1" else 11), 5, 12),
        )
        db.add(child)
        children.append(child)
    await db.flush()

    devices: dict[str, Device] = {}
    for child in children:
        device = Device(
            child_id=child.id,
            name=f"Tablette de {child.display_name}",
            platform=DevicePlatform.ANDROID,
            device_secret=proto.generate_device_secret(),
            app_version="1.0.0",
            os_version="Android 14",
            boot_id=f"boot-{child.display_name.lower()}",
            last_seen_at=clock_now(),
        )
        db.add(device)
        devices[child.display_name] = device
    await db.flush()

    # Regles : plus strictes en periode scolaire, evaluation obligatoire en vacances.
    db.add(
        PolicyProfile(
            family_id=family.id,
            period_type=PeriodType.SCHOOL,
            name="Semaine d'école",
            pass_score_pct=70.0,
            question_count=10,
            reward_minutes=90,
            daily_cap_minutes=120,
            cooldown_minutes=120,
            curfew_start="20:30",
            curfew_end="07:00",
        )
    )
    db.add(
        PolicyProfile(
            family_id=family.id,
            period_type=PeriodType.HOLIDAY,
            name="Vacances",
            pass_score_pct=65.0,
            question_count=12,
            reward_minutes=180,
            daily_cap_minutes=300,
            cooldown_minutes=90,
            allow_parent_direct_unlock=False,
            curfew_start="22:00",
            curfew_end="08:00",
        )
    )
    db.add(
        CalendarPeriod(
            family_id=family.id,
            label="Vacances de printemps",
            period_type=PeriodType.HOLIDAY,
            start_date=today - timedelta(days=9),
            end_date=today + timedelta(days=5),
        )
    )
    await db.flush()

    stats: dict[str, Any] = {"assessments": 0, "passed": 0, "sessions": 0, "skipped": {}}
    zone = ZoneInfo(family.timezone)

    for offset in range(days, 0, -1):
        # On se place a une heure credible (fin d'après-midi), sinon le
        # couvre-feu du foyer refuserait tous les deverrouillages.
        moment = (clock_now().astimezone(zone) - timedelta(days=offset)).replace(
            hour=rng.choice([16, 17, 18]), minute=rng.randrange(60), second=0, microsecond=0
        )
        with time_travel(moment - clock_now()):
            for child in children:
                if rng.random() > 0.72:  # tous les jours ne se ressemblent pas
                    continue
                profile = SKILL_PROFILES[child.display_name]
                policy = await resolve_policy(db, child)
                try:
                    exam = await assessment_svc.start_assessment(
                        db,
                        child=child,
                        policy=policy,
                        device=devices[child.display_name],
                        kind=AssessmentKind.UNLOCK
                        if rng.random() > 0.25
                        else AssessmentKind.PRACTICE,
                    )
                except Exception as exc:  # carence en cours, quota atteint : c'est la vie
                    reason = type(exc).__name__
                    stats["skipped"][reason] = stats["skipped"].get(reason, 0) + 1
                    continue

                # Recharge avec les items : les relations sont chargees a la demande.
                exam = await assessment_svc.get_assessment(db, exam.id)
                for item in exam.items:
                    question = await db.get(Question, item.question_id)
                    if question is None:
                        continue
                    # La probabilite de reussite depend de la matiere et de la difficulte.
                    base = profile.get(item.subject_code or "math", 0.7)
                    chance = max(0.05, min(0.98, base - 0.08 * (item.difficulty - 3)))
                    correct = rng.random() < chance
                    await assessment_svc.save_answer(
                        db,
                        exam,
                        item,
                        answer=_answer_for(question, correct, rng),
                        answer_mode=AnswerMode.HANDWRITTEN
                        if rng.random() < 0.15
                        else AnswerMode.ASSISTED,
                        time_spent_ms=rng.randint(12_000, 95_000),
                    )

                result = await assessment_svc.submit_assessment(
                    db,
                    child=child,
                    assessment=exam,
                    policy=policy,
                    device=devices[child.display_name],
                )
                stats["assessments"] += 1
                stats["passed"] += 1 if result.passed else 0

                if result.issued_code is not None:
                    try:
                        redeemed = await unlock.redeem_code(
                            db,
                            device=devices[child.display_name],
                            child=child,
                            code=result.issued_code.code,
                            policy=policy,
                        )
                        stats["sessions"] += 1
                        # L'enfant consommé 40 à 100 % du temps accordé.
                        used = int(redeemed.session.granted_ms * rng.uniform(0.4, 1.0))
                        finished_at = clock_now() + timedelta(milliseconds=used)
                        await screen_time.heartbeat(
                            db,
                            redeemed.session,
                            monotonic_ms=used,
                            screen_on=True,
                            at=finished_at,
                        )
                        # L'enfant repose la tablette : on cloture la session
                        # plutot que de la laisser ouverte dans l'historique.
                        await screen_time.end_session(
                            db, redeemed.session, reason="child_stop", at=finished_at
                        )
                    except Exception as exc:
                        reason = type(exc).__name__
                        stats["skipped"][reason] = stats["skipped"].get(reason, 0) + 1
                await db.commit()

    # Une session ouverte à l'instant : le tableau de bord doit montrer un
    # minuteur qui tourne, pas seulement de l'historique.
    try:
        live_child = children[0]
        live_policy = await resolve_policy(db, live_child)
        live_code = await unlock.issue_code(
            db,
            child=live_child,
            device=devices[live_child.display_name],
            duration_minutes=60,
            kind=proto.UnlockKind.PARENT_BONUS,
            note="Session de démonstration",
        )
        live = await unlock.redeem_code(
            db,
            device=devices[live_child.display_name],
            child=live_child,
            code=live_code.code,
            policy=live_policy,
        )
        await screen_time.heartbeat(
            db,
            live.session,
            monotonic_ms=11 * 60_000,
            screen_on=True,
            at=clock_now() + timedelta(minutes=11),
        )
        stats["live_session"] = str(live.session.id)
    except Exception as exc:
        stats["skipped"][f"live:{type(exc).__name__}"] = 1

    # Un code d'appairage en attente, pour la demonstration de l'écran d'appairage.
    from app.models.device import PairingRequest

    code = generate_pairing_code()
    db.add(
        PairingRequest(
            child_id=children[0].id,
            created_by_parent_id=parent.id,
            code_hash=hash_opaque(code),
            expires_at=clock_now() + timedelta(days=1),
            suggested_name="Nouvelle tablette",
        )
    )
    await db.commit()

    logger.info("Foyer de démonstration créé : %s", stats)
    return {
        "created": True,
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "family_id": str(family.id),
        "children": [
            {"id": str(c.id), "name": c.display_name, "grade": c.grade_code, "xp": c.xp_balance}
            for c in children
        ],
        "devices": [
            {"id": str(d.id), "name": d.name, "secret": d.device_secret} for d in devices.values()
        ],
        "pairing_code": code,
        **stats,
    }
