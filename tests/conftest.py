"""Shared pytest fixtures for ARTEMIS tests."""

from __future__ import annotations

import pytest

from artemis.db.repository import ArtemisRepository
from artemis.models.brief import ResearchBrief
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


@pytest.fixture
def repo() -> ArtemisRepository:
    """Provide a fresh in-memory SQLite repository for each test."""
    repository = ArtemisRepository(":memory:")
    yield repository
    repository.close()


@pytest.fixture
def sample_provenance() -> SourceProvenance:
    return SourceProvenance(
        source_url="https://cs.cmu.edu/~faculty/aturing",
        source_name="cmu_faculty_directory",
        snippet="Alan Turing, Professor of Computer Science. Research: Computability and AI.",
        verification_status=VerificationStatus.VERIFIED,
    )


@pytest.fixture
def sample_professor(sample_provenance: SourceProvenance) -> Professor:
    return Professor(
        name="Dr. Ada Lovelace",
        title="Associate Professor",
        department="Computer Science",
        institution="University of Oxford",
        email="ada.lovelace@ox.ac.uk",
        email_status=VerificationStatus.VERIFIED,
        profile_url="https://www.ox.ac.uk/people/ada-lovelace",
        lab_url="https://computational-foundations.ox.ac.uk",
        scholar_url="https://scholar.google.com/citations?user=sample123",
        research_interests=["Algorithmic Systems", "Mathematical Computation"],
        sources=[sample_provenance],
    )


@pytest.fixture
def sample_paper(sample_provenance: SourceProvenance) -> Paper:
    return Paper(
        title="Notes on the Analytical Engine and Mechanical Intelligence",
        abstract="We investigate mechanical computation applied to general symbolic operations.",
        published_date="2023-11-15",
        year=2023,
        venue="ACM Computing Surveys",
        doi="10.1145/381234.567890",
        arxiv_id="2311.99999",
        openalex_id="W9876543210",
        url="https://doi.org/10.1145/381234.567890",
        pdf_url="https://arxiv.org/pdf/2311.99999.pdf",
        citation_count=42,
        author_names=["Ada Lovelace", "Charles Babbage"],
        sources=[sample_provenance],
    )


@pytest.fixture
def sample_evidence() -> ResumeEvidence:
    return ResumeEvidence(
        category=EvidenceCategory.PROJECT,
        title="Symbolic Math Evaluator in Python",
        description="Engineered an AST-based symbolic arithmetic and differentiation engine.",
        skills=["Python", "Compilers", "AST", "Symbolic Math"],
        key_achievements=[
            "Parsed and simplified 100+ algebraic formulations",
            "Benchmarked against SymPy with 2x lower memory overhead",
        ],
        source_reference="Résumé Section: Technical Projects / github.com/student/symbolic-math",
    )


@pytest.fixture
def sample_brief(
    sample_professor: Professor,
    sample_paper: Paper,
    sample_evidence: ResumeEvidence,
    sample_provenance: SourceProvenance,
) -> ResearchBrief:
    return ResearchBrief(
        professor_id=sample_professor.id,
        paper_id=sample_paper.id,
        headline="Symbolic Execution and Machine Foundations Alignment",
        summary="Dr. Lovelace's 2023 paper explores mechanical foundations of symbolic computation.",
        core_contributions=[
            "Formalization of instruction pipelines for symbolic algebra",
            "Proof of extensibility to non-numeric manipulation",
        ],
        methodology="Formal semantic modeling and execution trace validation.",
        potential_alignment="Directly aligns with student's AST engine project in symbolic simplification.",
        matched_evidence_ids=[sample_evidence.id],
        open_questions=[
            "How could modern AST transformations be applied to minimize register allocation in the proposed pipeline?"
        ],
        confidence_score=0.95,
        confidence_notes="Verified against primary publication abstract and student project repo.",
        sources=[sample_provenance],
    )


@pytest.fixture
def sample_draft(
    sample_professor: Professor,
    sample_brief: ResearchBrief,
) -> EmailDraft:
    return EmailDraft(
        professor_id=sample_professor.id,
        brief_id=sample_brief.id,
        recipient_email=sample_professor.email,
        recipient_name="Professor Lovelace",
        subject="Inquiry regarding symbolic execution pipelines and prospective research",
        body=(
            "Dear Professor Lovelace,\n\n"
            "I recently read your 2023 ACM paper on the Analytical Engine and was intrigued by your "
            "formalization of symbolic instruction pipelines. During my recent work on an AST-based "
            "algebraic evaluator, I observed similar bottlenecks when parsing non-numeric symbols.\n\n"
            "I would welcome the opportunity to discuss your ongoing work and whether there might be "
            "room for a student researcher in your group.\n\n"
            "Sincerely,\nStudent"
        ),
        rationale="Connects AST evaluator project directly to the professor's 2023 paper.",
        status=EmailDraftStatus.DRAFT_PENDING,
        verification_notes="Email verified against University of Oxford official staff listing.",
    )
