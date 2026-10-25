"""Integration tests for ARTEMIS SQLite repository layer."""

from __future__ import annotations

import pytest

from artemis.db.repository import ArtemisRepository
from artemis.models.brief import ResearchBrief
from artemis.models.common import VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


class TestProfessorRepository:
    def test_create_and_get_professor(
        self, repo: ArtemisRepository, sample_professor: Professor
    ) -> None:
        created = repo.create_professor(sample_professor)
        assert created.id == sample_professor.id

        retrieved = repo.get_professor(sample_professor.id)
        assert retrieved is not None
        assert retrieved.name == sample_professor.name
        assert retrieved.institution == sample_professor.institution
        assert retrieved.email == sample_professor.email
        assert retrieved.email_status == VerificationStatus.VERIFIED
        assert retrieved.research_interests == sample_professor.research_interests
        assert len(retrieved.sources) == 1
        assert retrieved.sources[0].source_url == sample_professor.sources[0].source_url

    def test_get_nonexistent_professor(self, repo: ArtemisRepository) -> None:
        assert repo.get_professor("non_existent_id") is None

    def test_update_professor(
        self, repo: ArtemisRepository, sample_professor: Professor
    ) -> None:
        repo.create_professor(sample_professor)

        sample_professor.title = "Full Professor"
        sample_professor.research_interests.append("Quantum Foundations")
        updated = repo.update_professor(sample_professor)

        assert updated.title == "Full Professor"
        retrieved = repo.get_professor(sample_professor.id)
        assert retrieved is not None
        assert retrieved.title == "Full Professor"
        assert "Quantum Foundations" in retrieved.research_interests

    def test_update_nonexistent_professor_raises(
        self, repo: ArtemisRepository, sample_professor: Professor
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            repo.update_professor(sample_professor)

    def test_list_professors(
        self, repo: ArtemisRepository, sample_professor: Professor
    ) -> None:
        prof2 = Professor(
            name="Dr. Claude Shannon",
            institution="MIT",
            email="shannon@mit.edu",
        )
        repo.create_professor(sample_professor)
        repo.create_professor(prof2)

        all_profs = repo.list_professors()
        assert len(all_profs) == 2

        oxford_profs = repo.list_professors(institution="University of Oxford")
        assert len(oxford_profs) == 1
        assert oxford_profs[0].name == "Dr. Ada Lovelace"

        mit_profs = repo.list_professors(institution="MIT")
        assert len(mit_profs) == 1
        assert mit_profs[0].name == "Dr. Claude Shannon"

    def test_delete_professor(
        self, repo: ArtemisRepository, sample_professor: Professor
    ) -> None:
        repo.create_professor(sample_professor)
        assert repo.delete_professor(sample_professor.id) is True
        assert repo.get_professor(sample_professor.id) is None
        assert repo.delete_professor(sample_professor.id) is False


class TestPaperRepository:
    def test_create_and_get_paper(
        self, repo: ArtemisRepository, sample_paper: Paper
    ) -> None:
        repo.create_paper(sample_paper)
        retrieved = repo.get_paper(sample_paper.id)
        assert retrieved is not None
        assert retrieved.title == sample_paper.title
        assert retrieved.doi == sample_paper.doi
        assert retrieved.author_names == ["Ada Lovelace", "Charles Babbage"]
        assert len(retrieved.sources) == 1

    def test_update_paper(
        self, repo: ArtemisRepository, sample_paper: Paper
    ) -> None:
        repo.create_paper(sample_paper)
        sample_paper.citation_count = 105
        repo.update_paper(sample_paper)

        retrieved = repo.get_paper(sample_paper.id)
        assert retrieved is not None
        assert retrieved.citation_count == 105

    def test_list_and_delete_paper(
        self, repo: ArtemisRepository, sample_paper: Paper
    ) -> None:
        repo.create_paper(sample_paper)
        assert len(repo.list_papers()) == 1
        assert repo.delete_paper(sample_paper.id) is True
        assert len(repo.list_papers()) == 0

    def test_link_professor_paper(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)

        repo.link_professor_paper(sample_professor.id, sample_paper.id, "primary_author")

        papers = repo.get_papers_by_professor(sample_professor.id)
        assert len(papers) == 1
        assert papers[0].id == sample_paper.id

        # Unlink
        assert repo.unlink_professor_paper(sample_professor.id, sample_paper.id) is True
        assert len(repo.get_papers_by_professor(sample_professor.id)) == 0


class TestResumeEvidenceRepository:
    def test_create_and_get_evidence(
        self, repo: ArtemisRepository, sample_evidence: ResumeEvidence
    ) -> None:
        repo.create_evidence(sample_evidence)
        retrieved = repo.get_evidence(sample_evidence.id)
        assert retrieved is not None
        assert retrieved.title == sample_evidence.title
        assert retrieved.category == EvidenceCategory.PROJECT
        assert "AST" in retrieved.skills
        assert len(retrieved.key_achievements) == 2

    def test_update_evidence(
        self, repo: ArtemisRepository, sample_evidence: ResumeEvidence
    ) -> None:
        repo.create_evidence(sample_evidence)
        sample_evidence.title = "Advanced AST Symbolic Evaluator"
        repo.update_evidence(sample_evidence)

        retrieved = repo.get_evidence(sample_evidence.id)
        assert retrieved is not None
        assert retrieved.title == "Advanced AST Symbolic Evaluator"

    def test_list_evidence_by_category(
        self, repo: ArtemisRepository, sample_evidence: ResumeEvidence
    ) -> None:
        ev2 = ResumeEvidence(
            category=EvidenceCategory.RESEARCH_EXPERIENCE,
            title="Undergraduate Research Assistant",
            description="Analyzed memory access patterns in distributed storage engines.",
            skills=["C++", "Cache Simulation"],
        )
        repo.create_evidence(sample_evidence)
        repo.create_evidence(ev2)

        all_ev = repo.list_evidence()
        assert len(all_ev) == 2

        projects = repo.list_evidence(category=EvidenceCategory.PROJECT)
        assert len(projects) == 1
        assert projects[0].id == sample_evidence.id

        research = repo.list_evidence(category=EvidenceCategory.RESEARCH_EXPERIENCE)
        assert len(research) == 1
        assert research[0].id == ev2.id

    def test_delete_evidence(
        self, repo: ArtemisRepository, sample_evidence: ResumeEvidence
    ) -> None:
        repo.create_evidence(sample_evidence)
        assert repo.delete_evidence(sample_evidence.id) is True
        assert repo.get_evidence(sample_evidence.id) is None


class TestResearchBriefRepository:
    def test_create_and_get_brief(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)

        repo.create_brief(sample_brief)
        retrieved = repo.get_brief(sample_brief.id)

        assert retrieved is not None
        assert retrieved.headline == sample_brief.headline
        assert retrieved.confidence_score == 0.95
        assert len(retrieved.core_contributions) == 2
        assert len(retrieved.open_questions) == 1

    def test_update_brief(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)
        repo.create_brief(sample_brief)

        sample_brief.confidence_score = 0.99
        sample_brief.open_questions.append("Can we verify compiler passes formally?")
        repo.update_brief(sample_brief)

        retrieved = repo.get_brief(sample_brief.id)
        assert retrieved is not None
        assert retrieved.confidence_score == 0.99
        assert len(retrieved.open_questions) == 2

    def test_list_briefs_by_professor(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)
        repo.create_brief(sample_brief)

        briefs = repo.list_briefs_by_professor(sample_professor.id)
        assert len(briefs) == 1
        assert briefs[0].id == sample_brief.id

    def test_delete_brief(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)
        repo.create_brief(sample_brief)

        assert repo.delete_brief(sample_brief.id) is True
        assert repo.get_brief(sample_brief.id) is None


class TestEmailDraftRepository:
    def test_create_and_get_draft(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
        sample_draft: EmailDraft,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)
        repo.create_brief(sample_brief)

        repo.create_draft(sample_draft)
        retrieved = repo.get_draft(sample_draft.id)

        assert retrieved is not None
        assert retrieved.recipient_email == sample_professor.email
        assert retrieved.status == EmailDraftStatus.DRAFT_PENDING
        assert retrieved.gmail_draft_id is None

    def test_update_draft_status_to_gmail_synced(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_draft: EmailDraft,
    ) -> None:
        sample_draft.brief_id = None
        repo.create_professor(sample_professor)
        repo.create_draft(sample_draft)

        sample_draft.status = EmailDraftStatus.SYNCED_TO_GMAIL
        sample_draft.gmail_draft_id = "r-839182390123"
        repo.update_draft(sample_draft)

        retrieved = repo.get_draft(sample_draft.id)
        assert retrieved is not None
        assert retrieved.status == EmailDraftStatus.SYNCED_TO_GMAIL
        assert retrieved.gmail_draft_id == "r-839182390123"

    def test_list_drafts_filtered(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_draft: EmailDraft,
    ) -> None:
        prof2 = Professor(
            name="Dr. Claude Shannon",
            institution="MIT",
            email="shannon@mit.edu",
        )
        sample_draft.brief_id = None
        repo.create_professor(sample_professor)
        repo.create_professor(prof2)

        draft2 = EmailDraft(
            professor_id=prof2.id,
            recipient_email="shannon@mit.edu",
            recipient_name="Dr. Shannon",
            subject="Information Theory Discussion",
            body="Dear Dr. Shannon...",
            status=EmailDraftStatus.SYNCED_TO_GMAIL,
        )

        repo.create_draft(sample_draft)
        repo.create_draft(draft2)

        all_drafts = repo.list_drafts()
        assert len(all_drafts) == 2

        pending_drafts = repo.list_drafts(status=EmailDraftStatus.DRAFT_PENDING)
        assert len(pending_drafts) == 1
        assert pending_drafts[0].id == sample_draft.id

        prof2_drafts = repo.list_drafts(professor_id=prof2.id)
        assert len(prof2_drafts) == 1
        assert prof2_drafts[0].id == draft2.id

    def test_delete_draft(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_draft: EmailDraft,
    ) -> None:
        sample_draft.brief_id = None
        repo.create_professor(sample_professor)
        repo.create_draft(sample_draft)

        assert repo.delete_draft(sample_draft.id) is True
        assert repo.get_draft(sample_draft.id) is None


class TestForeignKeysAndCascades:
    def test_cascade_delete_professor_deletes_dependent_draft_and_brief(
        self,
        repo: ArtemisRepository,
        sample_professor: Professor,
        sample_paper: Paper,
        sample_brief: ResearchBrief,
        sample_draft: EmailDraft,
    ) -> None:
        repo.create_professor(sample_professor)
        repo.create_paper(sample_paper)
        repo.create_brief(sample_brief)
        repo.create_draft(sample_draft)
        repo.link_professor_paper(sample_professor.id, sample_paper.id)

        # Deleting professor should cascade delete their briefs and drafts and junction entries
        assert repo.delete_professor(sample_professor.id) is True

        assert repo.get_professor(sample_professor.id) is None
        assert repo.get_brief(sample_brief.id) is None
        assert repo.get_draft(sample_draft.id) is None
        assert repo.get_papers_by_professor(sample_professor.id) == []

        # The paper itself is an independent publication and should still exist
        assert repo.get_paper(sample_paper.id) is not None
