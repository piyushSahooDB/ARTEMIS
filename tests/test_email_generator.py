"""Unit tests for DraftGenerator: single-paper grounding, anti-hallucination, and conciseness."""

from __future__ import annotations

import json
import pytest

from artemis.brief.synthesizer import ResearchBriefSynthesizer
from artemis.email.generator import DraftGenerator
from artemis.llm.provider import MockLLMProvider
from artemis.models.brief import ResearchBrief
from artemis.models.common import VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


@pytest.fixture
def sample_professor() -> Professor:
    return Professor(
        name="Dr. Leslie Lamport",
        institution="Stanford University",
        email="lamport@stanford.edu",
        email_status=VerificationStatus.VERIFIED,
    )


@pytest.fixture
def sample_paper() -> Paper:
    return Paper(
        title="Scalable Multi-Paxos Consensus under Asynchronous Partitions",
        year=2024,
        venue="ACM TOCS",
        doi="10.1145/123456.789012",
        abstract="We investigate leader election and replicated state machines.",
    )


@pytest.fixture
def sample_brief(sample_professor: Professor, sample_paper: Paper) -> ResearchBrief:
    return ResearchBrief(
        professor_id=sample_professor.id,
        paper_id=sample_paper.id,
        headline="[Abstract-Based Brief] Scalable Multi-Paxos Consensus",
        summary="Investigates leader election and replicated state machines under asynchronous partitions.",
        core_contributions=["Novel pipelined consensus algorithm reducing message overhead."],
        potential_alignment="Student built Raft-based KV store in Go with state machine replication.",
        matched_evidence_ids=["evid_raft_1"],
        open_questions=["How does the pipelined variant maintain liveness during high-frequency failures?"],
        confidence_score=0.85,
    )


@pytest.fixture
def sample_evidence() -> list[ResumeEvidence]:
    return [
        ResumeEvidence(
            id="evid_raft_1",
            category=EvidenceCategory.PROJECT,
            title="Raft Distributed KV Store",
            description="Built a distributed key-value store in Go with Raft consensus.",
            skills=["Go", "Raft", "Consensus"],
            key_achievements=["Implemented leader election and log compaction"],
            verification_status=VerificationStatus.UNVERIFIED,
        )
    ]


class TestDraftGenerator:
    def test_generate_draft_grounded_success(
        self,
        sample_professor: Professor,
        sample_brief: ResearchBrief,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        generator = DraftGenerator(llm_provider=MockLLMProvider())

        draft = generator.generate_draft(
            professor=sample_professor,
            brief=sample_brief,
            paper=sample_paper,
            evidence=sample_evidence,
            student_name="Jane Doe",
        )

        assert isinstance(draft, EmailDraft)
        assert draft.status == EmailDraftStatus.DRAFT_PENDING
        assert draft.recipient_email == "lamport@stanford.edu"
        assert draft.recipient_name == "Dr. Leslie Lamport"
        assert "Jane Doe" in draft.body
        # Check conciseness: under 300 words
        word_count = len(draft.body.split())
        assert word_count <= 280

        # Verification notes must track grounding
        assert "Scalable Multi-Paxos" in draft.verification_notes
        assert "evid_raft_1" in draft.verification_notes

    def test_forbids_hallucinated_prior_contact_phrases(
        self,
        sample_professor: Professor,
        sample_brief: ResearchBrief,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        # LLM generated response with forbidden phrases
        hallucinated_body = (
            "Dear Professor,\n\n"
            "As we discussed in your lecture yesterday, I am following up on our conversation. "
            "I saw your job posting for a research assistant on consensus. "
            "In my project on Raft, I implemented log compaction.\n\n"
            "Sincerely,\nStudent"
        )
        fake_response = json.dumps({
            "subject": "Research follow up",
            "body": hallucinated_body,
            "rationale": "Following up on talk",
            "verification_notes": "None",
        })
        mock_llm = MockLLMProvider(default_response=fake_response)
        generator = DraftGenerator(llm_provider=mock_llm)

        draft = generator.generate_draft(
            professor=sample_professor,
            brief=sample_brief,
            paper=sample_paper,
            evidence=sample_evidence,
        )

        # Forbidden phrases must be sanitized
        body_lower = draft.body.lower()
        assert "as we discussed" not in body_lower
        assert "following up on our conversation" not in body_lower
        assert "saw your job posting" not in body_lower

    def test_unverified_missing_email_generates_safety_warning(
        self,
        sample_brief: ResearchBrief,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        prof_without_email = Professor(
            name="Unknown Prof",
            institution="Indian Institute of Technology Kanpur",
            email=None,
            email_status=VerificationStatus.UNVERIFIED,
        )
        generator = DraftGenerator(llm_provider=MockLLMProvider())

        draft = generator.generate_draft(
            professor=prof_without_email,
            brief=sample_brief,
            paper=sample_paper,
            evidence=sample_evidence,
        )

        assert "WARNING" in draft.verification_notes
        assert "unverified" in draft.verification_notes.lower()
        assert "@" in draft.recipient_email  # Meets email format validation

    def test_deterministic_fallback_on_malformed_llm_output(
        self,
        sample_professor: Professor,
        sample_brief: ResearchBrief,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        broken_llm = MockLLMProvider(default_response="<< BROKEN RAW STRING >>")
        generator = DraftGenerator(llm_provider=broken_llm)

        draft = generator.generate_draft(
            professor=sample_professor,
            brief=sample_brief,
            paper=sample_paper,
            evidence=sample_evidence,
            student_name="Alice",
        )

        assert isinstance(draft, EmailDraft)
        assert draft.status == EmailDraftStatus.DRAFT_PENDING
        assert "Scalable Multi-Paxos" in draft.body
        assert "Alice" in draft.body
