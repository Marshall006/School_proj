"""Vocabulaire du domaine. Toutes les valeurs sont stockees en clair (VARCHAR)."""

from __future__ import annotations

from enum import StrEnum


class ParentRole(StrEnum):
    OWNER = "owner"
    GUARDIAN = "guardian"
    VIEWER = "viewer"


class PeriodType(StrEnum):
    """Contexte calendaire : conditionne le profil de regles applique."""

    SCHOOL = "school"  # periode scolaire : deverrouillage parental direct
    WEEKEND = "weekend"
    HOLIDAY = "holiday"  # vacances : deverrouillage par evaluation


class DevicePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    WEB = "web"


class DeviceStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    LOST = "lost"


class QuestionType(StrEnum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    TRUE_FALSE = "true_false"
    NUMERIC = "numeric"
    SHORT_TEXT = "short_text"
    FILL_BLANK = "fill_blank"
    ORDERING = "ordering"
    MATCHING = "matching"
    EXPRESSION = "expression"  # saisie assistee : fractions, symboles, operations posees
    HANDWRITTEN = "handwritten"  # ardoise : correction assistee puis validation parentale
    VOICE = "voice"  # V2 : lecture a voix haute, langues vivantes


#: Types dont la correction automatique est fiable a 100 %.
AUTO_GRADED_TYPES = frozenset(
    {
        QuestionType.MCQ_SINGLE,
        QuestionType.MCQ_MULTI,
        QuestionType.TRUE_FALSE,
        QuestionType.NUMERIC,
        QuestionType.SHORT_TEXT,
        QuestionType.FILL_BLANK,
        QuestionType.ORDERING,
        QuestionType.MATCHING,
        QuestionType.EXPRESSION,
    }
)


class AnswerMode(StrEnum):
    """Comment l'enfant a repondu (l'application propose les deux)."""

    ASSISTED = "assisted"  # composants graphiques : pave numerique, fractions, glisser-deposer
    HANDWRITTEN = "handwritten"  # ardoise libre au doigt ou au stylet
    VOICE = "voice"


class AssessmentKind(StrEnum):
    UNLOCK = "unlock"  # pour obtenir un code d'acces
    PRACTICE = "practice"  # volontaire : rapporte des XP, pas de code
    PARENT_ASSIGNED = "parent_assigned"  # devoir pousse par le parent
    PLACEMENT = "placement"  # test de positionnement initial


class AssessmentStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    NEEDS_REVIEW = "needs_review"  # au moins une reponse manuscrite a valider
    EXPIRED = "expired"
    ABANDONED = "abandoned"


class UnlockCodeStatus(StrEnum):
    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ScreenSessionState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"  # ecran eteint : le minuteur s'arrete
    ENDED = "ended"
    EXPIRED = "expired"
    REVOKED = "revoked"  # coupure a distance par le parent


class ScreenEventType(StrEnum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    HEARTBEAT = "heartbeat"
    EXTEND = "extend"
    END = "end"
    EXPIRE = "expire"
    REVOKE = "revoke"
    TAMPER = "tamper"  # horloge manipulee, redemarrage suspect...
    OFFLINE_GAP = "offline_gap"  # reconciliation apres une periode hors ligne


class LockoutReason(StrEnum):
    FAILED_ASSESSMENT = "failed_assessment"  # temps de carence obligatoire
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    DAILY_CAP = "daily_cap"
    CURFEW = "curfew"
    PARENT_MANUAL = "parent_manual"
    TAMPER_DETECTED = "tamper_detected"
    CODE_BRUTEFORCE = "code_bruteforce"


class XPReason(StrEnum):
    CORRECT_ANSWER = "correct_answer"
    ASSESSMENT_PASSED = "assessment_passed"
    PERFECT_SCORE = "perfect_score"
    STREAK_BONUS = "streak_bonus"
    DAILY_GOAL = "daily_goal"
    WEAKNESS_CLEARED = "weakness_cleared"
    PARENT_GRANT = "parent_grant"
    REDEEM = "redeem"  # conversion en minutes d'ecran (delta negatif)
    ADJUSTMENT = "adjustment"


class MasteryBand(StrEnum):
    UNKNOWN = "unknown"
    FRAGILE = "fragile"
    EN_COURS = "en_cours"
    ACQUIS = "acquis"
    EXPERT = "expert"
