"""Domain models for ARTEMIS."""

from artemis.models.brief import ResearchBrief
from artemis.models.common import (
    SourceProvenance,
    VerificationStatus,
    utc_now,
)
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence
from artemis.models.run import ScoutingRun

__all__ = [
    "EvidenceCategory",
    "EmailDraft",
    "EmailDraftStatus",
    "Paper",
    "Professor",
    "ResearchBrief",
    "ResumeEvidence",
    "ScoutingRun",
    "SourceProvenance",
    "VerificationStatus",
    "utc_now",
]
