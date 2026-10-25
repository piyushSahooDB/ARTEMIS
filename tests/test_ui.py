"""Unit and integration tests for A.R.T.E.M.I.S. UI modules and quality checks."""

import pytest

from artemis.db import ArtemisRepository
from artemis.models import EmailDraft, Paper, Professor, ResearchBrief, ResumeEvidence, ScoutingRun
from artemis.ui.components.quality import FORBIDDEN_PHRASES, analyze_email_draft
from artemis.ui.state import get_active_llm_provider


class TestQualityControl:
    """Test suite for cold-email quality control and anti-hallucination auditor."""

    def test_clean_concise_draft_passes(self):
        """A well-structured, concise draft referencing a valid paper should pass."""
        body = (
            "Dear Professor Kumar,\n\n"
            "I recently studied your research on Approximation Algorithms for Graph Clustering "
            "and found the theoretical bounds compelling. In my undergraduate coursework and projects, "
            "I implemented parallel graph partitioning algorithms with strong empirical results.\n\n"
            "I would welcome the opportunity to discuss prospective research internships in your group "
            "for the upcoming summer semester.\n\n"
            "Sincerely,\nStudent"
        )
        report = analyze_email_draft(
            body=body,
            subject="Undergraduate Research Inquiry: Graph Clustering",
            recipient_email="kumar@cse.iitd.ac.in",
            paper_title="Approximation Algorithms for Graph Clustering",
            email_verification_status="verified",
        )

        assert report.passed is True
        assert report.is_word_count_ok is True
        assert report.word_count < 300
        assert len(report.hallucination_warnings) == 0
        assert len(report.recipient_warnings) == 0
        assert len(report.grounding_warnings) == 0

    def test_detects_forbidden_assumed_familiarity_phrases(self):
        """Detects phrases implying non-existent prior conversations or job advertisements."""
        for phrase in ["as we discussed", "per our conversation", "saw your job posting", "in your lecture"]:
            body = (
                f"Dear Professor,\n\nFurther to {phrase}, I am writing to apply for the position. "
                "I have extensive experience in machine learning algorithms and software architecture. "
                "Looking forward to hearing from you soon.\n\nBest,\nStudent"
            )
            report = analyze_email_draft(
                body=body,
                subject="Research Inquiry",
                recipient_email="prof@inst.edu",
            )
            assert report.passed is False
            assert any(phrase in w for w in report.hallucination_warnings)

    def test_detects_unfilled_placeholders(self):
        """Flags unfilled template markers such as [Insert Project Name]."""
        body = (
            "Dear Professor,\n\n"
            "I read your paper and really liked it. In my project [Your Project Here], I worked on similar topics.\n\n"
            "Sincerely,\n[Student Name]"
        )
        report = analyze_email_draft(
            body=body,
            recipient_email="prof@iit.ac.in",
        )
        assert any("Unfilled template brackets" in w for w in report.hallucination_warnings)

    def test_flags_excessive_word_count(self):
        """Flags emails exceeding 300 words."""
        long_body = "word " * 320
        report = analyze_email_draft(
            body=long_body,
            recipient_email="prof@iit.ac.in",
        )
        assert report.is_word_count_ok is False
        assert "Too long" in report.word_count_feedback

    def test_flags_too_short_word_count(self):
        """Flags emails shorter than 40 words."""
        short_body = "Hi Professor, give me an internship please. Thanks."
        report = analyze_email_draft(
            body=short_body,
            recipient_email="prof@iit.ac.in",
        )
        assert report.is_word_count_ok is False
        assert "Too short" in report.word_count_feedback

    def test_flags_placeholder_and_unverified_emails(self):
        """Warns on placeholder domains and unverified email addresses."""
        report = analyze_email_draft(
            body="Valid email body " * 15,
            recipient_email="prof@example.com",
            email_verification_status="unverified",
        )
        assert any("Placeholder email address" in w for w in report.recipient_warnings)

        report_unverified = analyze_email_draft(
            body="Valid email body " * 15,
            recipient_email="prof@iitd.ac.in",
            email_verification_status="unverified",
        )
        assert any("unverified" in w for w in report_unverified.recipient_warnings)

    def test_flags_missing_recipient_email(self):
        """Flags absence of recipient email."""
        report = analyze_email_draft(
            body="Valid email body " * 15,
            recipient_email=None,
        )
        assert any("No recipient email" in w for w in report.recipient_warnings)

    def test_checks_paper_grounding_keywords(self):
        """Warns if the email text has no keywords from the referenced paper title."""
        report = analyze_email_draft(
            body="Dear Professor,\n\nI am writing about quantum physics and chemistry simulations. " * 5,
            subject="Research inquiry",
            recipient_email="prof@iit.ac.in",
            paper_title="Compiler Optimizations for Heterogeneous Distributed Systems",
        )
        assert any("does not appear to be cited" in w for w in report.grounding_warnings)


class TestUIStateAndRepositoryIntegration:
    """Test suite ensuring UI state and repository operations work seamlessly."""

    @pytest.fixture
    def memory_repo(self):
        return ArtemisRepository(db=":memory:")

    def test_scouting_run_persistence_and_retrieval(self, memory_repo):
        """Test recording and retrieving scouting runs for UI dashboard."""
        run = ScoutingRun(
            directory_url="https://homecse.iitd.ac.in/faculty/",
            keywords=["algorithms", "compilers"],
            faculty_found=5,
            papers_found=12,
            status="completed",
        )
        memory_repo.create_scouting_run(run)

        runs = memory_repo.list_scouting_runs()
        assert len(runs) == 1
        assert runs[0].faculty_found == 5
        assert runs[0].papers_found == 12
        assert runs[0].status == "completed"

    def test_llm_provider_factory_mock(self):
        """Test active LLM provider factory defaults to mock without API keys."""
        from artemis.llm.provider import MockLLMProvider

        provider = get_active_llm_provider("mock")
        assert isinstance(provider, MockLLMProvider)
