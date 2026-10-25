"""Unit tests for ResearchBriefSynthesizer: grounding, abstract labeling, and fabricated-claim rejection."""

from __future__ import annotations

import json
import pytest

from artemis.brief.synthesizer import ResearchBriefSynthesizer
from artemis.llm.provider import MockLLMProvider
from artemis.models.brief import ResearchBrief
from artemis.models.common import VerificationStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


@pytest.fixture
def sample_professor() -> Professor:
    return Professor(
        name="Dr. Leslie Lamport",
        institution="Stanford University",
        department="Computer Science",
        research_interests=["Distributed Systems", "Fault Tolerance", "Consensus"],
    )


@pytest.fixture
def sample_paper() -> Paper:
    return Paper(
        title="Scalable Multi-Paxos Consensus under Asynchronous Partitions",
        year=2024,
        venue="ACM TOCS",
        doi="10.1145/123456.789012",
        abstract="We investigate leader election and replicated state machines under wide-area network latency partitions.",
    )


@pytest.fixture
def sample_evidence() -> list[ResumeEvidence]:
    return [
        ResumeEvidence(
            id="evid_raft_1",
            category=EvidenceCategory.PROJECT,
            title="Raft Distributed KV Store",
            description="Built a distributed key-value store in Go with Raft consensus and state machine replication.",
            skills=["Go", "Raft", "Consensus", "Distributed Systems"],
            key_achievements=["Implemented leader election and log compaction"],
            verification_status=VerificationStatus.UNVERIFIED,
            raw_snippet="Implemented Raft consensus in Go...",
        ),
        ResumeEvidence(
            id="evid_cv_1",
            category=EvidenceCategory.PROJECT,
            title="Medical Image CNN",
            description="Trained PyTorch convolutional neural network for X-ray classification.",
            skills=["Python", "PyTorch", "Computer Vision"],
            key_achievements=["Achieved 0.90 AUROC"],
            verification_status=VerificationStatus.UNVERIFIED,
            raw_snippet="Trained PyTorch CNN on chest X-rays...",
        ),
    ]


class TestResearchBriefSynthesizer:
    def test_synthesize_abstract_only_paper_enforces_labeling(
        self,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        mock_llm = MockLLMProvider()
        synthesizer = ResearchBriefSynthesizer(llm_provider=mock_llm)

        # full_text is None -> abstract-only paper
        brief = synthesizer.synthesize(
            professor=sample_professor,
            paper=sample_paper,
            evidence=sample_evidence,
            full_text=None,
        )

        assert isinstance(brief, ResearchBrief)
        assert brief.headline.startswith("[Abstract-Based Brief]")
        assert "abstract" in brief.methodology.lower()
        assert len(brief.limitations) > 0
        assert any("abstract" in l.lower() for l in brief.limitations)
        assert brief.confidence_score >= 0.70
        assert "evid_raft_1" in brief.matched_evidence_ids

    def test_reject_fabricated_evidence_ids(
        self,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        # LLM hallucinates an evidence ID not present in student's résumé
        hallucinated_response = json.dumps({
            "headline": "Scalable Consensus",
            "summary": "Summary of paper",
            "core_contributions": ["Novel consensus algorithm"],
            "methodology": "Empirical evaluation",
            "limitations": ["Limited to 50 nodes"],
            "potential_alignment": "Student is a pioneer in quantum consensus",
            "matched_evidence_ids": ["evid_fake_invented_999", "evid_raft_1"],
            "gaps": ["None"],
            "open_questions": ["Question 1"],
            "confidence_score": 0.95,
            "confidence_notes": "Grounding verified",
        })
        mock_llm = MockLLMProvider(default_response=hallucinated_response)
        synthesizer = ResearchBriefSynthesizer(llm_provider=mock_llm)

        brief = synthesizer.synthesize(
            professor=sample_professor,
            paper=sample_paper,
            evidence=sample_evidence,
        )

        # Hallucinated ID must be rejected; authentic ID retained
        assert "evid_fake_invented_999" not in brief.matched_evidence_ids
        assert "evid_raft_1" in brief.matched_evidence_ids

    def test_missing_or_unrelated_evidence_returns_uncertainty(
        self,
        sample_professor: Professor,
        sample_paper: Paper,
    ) -> None:
        # Only unrelated evidence (Computer Vision evidence for a Distributed Systems paper)
        unrelated_evidence = [
            ResumeEvidence(
                id="evid_cv_only",
                category=EvidenceCategory.PROJECT,
                title="Medical Image CNN",
                description="Trained PyTorch convolutional neural network for X-ray classification.",
                skills=["Python", "PyTorch", "Computer Vision"],
                verification_status=VerificationStatus.UNVERIFIED,
            )
        ]
        # LLM returns no matched evidence
        response_no_match = json.dumps({
            "headline": "[Abstract-Based Brief] Scalable Multi-Paxos",
            "summary": "Summary of paper",
            "core_contributions": ["Paxos protocol"],
            "methodology": "Abstract only",
            "limitations": ["Abstract only"],
            "potential_alignment": "Student has no distributed systems experience",
            "matched_evidence_ids": [],
            "gaps": ["Lacks distributed systems and Go coursework/projects"],
            "open_questions": ["How to handle network partitions?"],
            "confidence_score": 0.25,
            "confidence_notes": "No matching evidence in student background",
        })
        mock_llm = MockLLMProvider(default_response=response_no_match)
        synthesizer = ResearchBriefSynthesizer(llm_provider=mock_llm)

        brief = synthesizer.synthesize(
            professor=sample_professor,
            paper=sample_paper,
            evidence=unrelated_evidence,
        )

        assert brief.confidence_score <= 0.35
        assert brief.matched_evidence_ids == []
        assert len(brief.gaps) > 0
        assert "insufficient" in brief.confidence_notes.lower() or "no" in brief.confidence_notes.lower()

    def test_deterministic_fallback_on_malformed_llm_json(
        self,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_evidence: list[ResumeEvidence],
    ) -> None:
        mock_llm = MockLLMProvider(default_response="INVALID NON-JSON TEXT FROM MODEL")
        synthesizer = ResearchBriefSynthesizer(llm_provider=mock_llm)

        brief = synthesizer.synthesize(
            professor=sample_professor,
            paper=sample_paper,
            evidence=sample_evidence,
        )

        assert isinstance(brief, ResearchBrief)
        assert brief.headline.startswith("[Abstract-Based Brief]")
        assert len(brief.core_contributions) > 0
        assert len(brief.open_questions) >= 1
