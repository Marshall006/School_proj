"""Point d'entree unique : importer ce module enregistre toutes les tables."""

from app.db.base import Base
from app.models.access import Lockout, ScreenEvent, ScreenSession, UnlockCode
from app.models.assessment import Assessment, AssessmentItem
from app.models.audit import AuditEvent
from app.models.content import GradeLevel, Question, Subject, Topic
from app.models.device import Device, PairingRequest
from app.models.enums import (
    AnswerMode,
    AssessmentKind,
    AssessmentStatus,
    DevicePlatform,
    DeviceStatus,
    LockoutReason,
    MasteryBand,
    ParentRole,
    PeriodType,
    QuestionType,
    ScreenEventType,
    ScreenSessionState,
    UnlockCodeStatus,
    XPReason,
)
from app.models.family import Child, Family, Parent, RefreshToken
from app.models.policy import CalendarPeriod, PolicyProfile
from app.models.progress import Mastery, XPLedgerEntry

__all__ = [
    "AnswerMode",
    "Assessment",
    "AssessmentItem",
    "AssessmentKind",
    "AssessmentStatus",
    "AuditEvent",
    "Base",
    "CalendarPeriod",
    "Child",
    "Device",
    "DevicePlatform",
    "DeviceStatus",
    "Family",
    "GradeLevel",
    "Lockout",
    "LockoutReason",
    "Mastery",
    "MasteryBand",
    "PairingRequest",
    "Parent",
    "ParentRole",
    "PeriodType",
    "PolicyProfile",
    "Question",
    "QuestionType",
    "RefreshToken",
    "ScreenEvent",
    "ScreenEventType",
    "ScreenSession",
    "ScreenSessionState",
    "Subject",
    "Topic",
    "UnlockCode",
    "UnlockCodeStatus",
    "XPLedgerEntry",
    "XPReason",
]
