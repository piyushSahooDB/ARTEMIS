"""Unit tests for ARTEMIS Pydantic domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from artemis.models.brief import ResearchBrief
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


class TestCommonModels:
    def test_source_provenance_defaults(self) -> None:
        prov = SourceProvenance(
            source_url="https://example.edu/faculty/alice",
            source_name="faculty_page",
        )
        assert prov.source_url == "https://example.edu/faculty/alice"
        assert prov.source_name == "faculty_page"
        assert prov.verification_status == VerificationStatus.UNVERIFIED
        assert prov.snippet is None
        assert prov.extracted_at is not None

    def test_source_provenance_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SourceProvenance(
                source_url="https://example.edu",
                source_name="faculty_page",
                unrecognized_field="illegal",  # type: ignore[call-arg]
            )


class TestProfessorModel:
    def test_valid_professor(self, sample_professor: Professor) -> None:
        assert sample_professor.name == "Dr. Ada Lovelace"
        assert sample_professor.institution == "University of Oxford"
        assert sample_professor.email == "ada.lovelace@ox.ac.uk"
        assert sample_professor.email_status == VerificationStatus.VERIFIED
        assert len(sample_professor.sources) == 1
        assert sample_professor.id.startswith("prof_")

    def test_professor_empty_name_fails(self) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            Professor(name="   ", institution="MIT")

    def test_professor_empty_institution_fails(self) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            Professor(name="Dr. Shannon", institution="")

    def test_professor_allows_none_email(self) -> None:
        # Crucial anti-hallucination test: never require an unconfirmed email
        prof = Professor(name="Dr. Shannon", institution="MIT", email=None)
        assert prof.email is None
        assert prof.email_status == VerificationStatus.UNVERIFIED

    def test_professor_invalid_email_format(self) -> None:
        with pytest.raises(ValidationError, match="Invalid email address format"):
            Professor(name="Dr. Shannon", institution="MIT", email="invalid-address")

    def test_professor_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Professor(
                name="Dr. Shannon",
                institution="MIT",
                hallucinated_bio="Not allowed",  # type: ignore[call-arg]
            )


class TestPaperModel:
    def test_valid_paper(self, sample_paper: Paper) -> None:
        assert sample_paper.title.startswith("Notes on the Analytical Engine")
        assert sample_paper.year == 2023
        assert sample_paper.citation_count == 42
        assert sample_paper.id.startswith("paper_")

    def test_paper_empty_title_fails(self) -> None:
        with pytest.raises(ValidationError, match="Paper title must not be empty"):
            Paper(title="  \n  ")

    def test_paper_negative_citation_count_fails(self) -> None:
        with pytest.raises(ValidationError, match="Citation count must be non-negative"):
            Paper(title="A Study of Logic", citation_count=-5)

    def test_paper_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Paper(
                title="A Study of Logic",
                random_meta="value",  # type: ignore[call-arg]
            )


class TestResumeEvidenceModel:
    def test_valid_evidence(self, sample_evidence: ResumeEvidence) -> None:
        assert sample_evidence.category == EvidenceCategory.PROJECT
        assert sample_evidence.title == "Symbolic Math Evaluator in Python"
        assert len(sample_evidence.skills) == 4
        assert sample_evidence.id.startswith("evid_")

    def test_evidence_empty_title_fails(self) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            ResumeEvidence(title="", description="Details here")

    def test_evidence_empty_description_fails(self) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            ResumeEvidence(title="Project Alpha", description="   ")

    def test_evidence_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ResumeEvidence(
                title="Project",
                description="Built an app",
                extra_payload=123,  # type: ignore[call-arg]
            )


class TestResearchBriefModel:
    def test_valid_brief(self, sample_brief: ResearchBrief) -> None:
        assert sample_brief.headline.startswith("Symbolic Execution")
        assert sample_brief.confidence_score == 0.95
        assert len(sample_brief.core_contributions) == 2
        assert len(sample_brief.matched_evidence_ids) == 1
        assert sample_brief.id.startswith("brief_")

    def test_brief_confidence_out_of_bounds_fails(
        self, sample_professor: Professor
    ) -> None:
        with pytest.raises(ValidationError):
            ResearchBrief(
                professor_id=sample_professor.id,
                headline="Topic",
                summary="Summary text",
                potential_alignment="Alignment rationale",
                confidence_score=1.5,  # Exceeds max 1.0
            )

        with pytest.raises(ValidationError):
            ResearchBrief(
                professor_id=sample_professor.id,
                headline="Topic",
                summary="Summary text",
                potential_alignment="Alignment rationale",
                confidence_score=-0.1,  # Below min 0.0
            )

    def test_brief_empty_required_fields_fail(self) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            ResearchBrief(
                professor_id="prof_123",
                headline="Headline",
                summary="",  # Empty summary
                potential_alignment="Alignment",
            )


class TestEmailDraftModel:
    def test_valid_draft(self, sample_draft: EmailDraft) -> None:
        assert sample_draft.status == EmailDraftStatus.DRAFT_PENDING
        assert sample_draft.recipient_email == "ada.lovelace@ox.ac.uk"
        assert "Inquiry regarding" in sample_draft.subject
        assert sample_draft.gmail_draft_id is None
        assert sample_draft.id.startswith("draft_")

    def test_draft_invalid_email_fails(self, sample_professor: Professor) -> None:
        with pytest.raises(ValidationError, match="Invalid email address"):
            EmailDraft(
                professor_id=sample_professor.id,
                recipient_email="not-an-email",
                recipient_name="Dr. Lovelace",
                subject="Hello",
                body="Message body",
            )

    def test_draft_empty_subject_fails(self, sample_professor: Professor) -> None:
        with pytest.raises(ValidationError, match="Field must not be empty"):
            EmailDraft(
                professor_id=sample_professor.id,
                recipient_email="prof@example.edu",
                recipient_name="Dr. Lovelace",
                subject="   ",
                body="Message body",
            )
