"""Unit and integration tests for Milestone 3 service methods and CLI subcommands."""

from __future__ import annotations

from pathlib import Path
import httpx
import pytest

from artemis.cli import format_brief, format_draft, format_evidence_table, main
from artemis.crawler.client import PoliteHttpClient
from artemis.db.repository import ArtemisRepository
from artemis.llm.provider import MockLLMProvider
from artemis.models.brief import ResearchBrief
from artemis.models.common import VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence
from artemis.service import ArtemisScoutingService


@pytest.fixture
def sample_resume_file(tmp_path: Path) -> Path:
    cv = tmp_path / "student_cv.md"
    cv.write_text(
        """# John Doe
john.doe@university.edu

## Technical Skills
Languages: Python, Go, C++, SQL
Tools: Docker, Linux, Git, PyTorch

## Relevant Coursework
Distributed Systems, Computer Networks, Operating Systems

## Projects
### Raft Consensus Replicated Store
- Built distributed KV store in Go implementing Raft leader election and log compaction.
- Tested partition tolerance under simulated node dropouts.
""",
        encoding="utf-8",
    )
    return cv


class TestMilestone3Service:
    def test_ingest_resume_and_persistence(self, sample_resume_file: Path) -> None:
        with ArtemisRepository(":memory:") as repo:
            with ArtemisScoutingService(repository=repo) as service:
                items = service.ingest_resume(sample_resume_file, persist=True)

                assert len(items) >= 2
                assert all(isinstance(it, ResumeEvidence) for it in items)
                assert all(it.verification_status == VerificationStatus.UNVERIFIED for it in items)

                # Check persistence
                stored = repo.list_evidence()
                assert len(stored) == len(items)

                # Re-ingesting should update idempotently without creating duplicates
                items_run2 = service.ingest_resume(sample_resume_file, persist=True)
                assert len(repo.list_evidence()) == len(items)

    def test_synthesize_brief_and_generate_draft_end_to_end(self, sample_resume_file: Path) -> None:
        with ArtemisRepository(":memory:") as repo:
            prof = Professor(
                name="Dr. Leslie Lamport",
                institution="Stanford University",
                email="lamport@stanford.edu",
                email_status=VerificationStatus.VERIFIED,
                research_interests=["Distributed Systems"],
            )
            paper = Paper(
                title="Paxos Made Simple",
                year=2001,
                venue="ACM SIGACT News",
                doi="10.1145/568425.568433",
                abstract="The Paxos algorithm for implementing a fault-tolerant distributed system.",
            )
            repo.create_professor(prof)
            repo.create_paper(paper)
            repo.link_professor_paper(prof.id, paper.id)

            mock_llm = MockLLMProvider()
            with ArtemisScoutingService(repository=repo, llm_provider=mock_llm) as service:
                # 1. Ingest résumé
                evidence = service.ingest_resume(sample_resume_file, persist=True)
                assert len(evidence) >= 2

                # 2. Synthesize research brief
                brief = service.synthesize_brief(prof.id, paper.id, persist=True)
                assert isinstance(brief, ResearchBrief)
                assert brief.headline.startswith("[Abstract-Based Brief]")
                assert len(brief.core_contributions) >= 1
                assert repo.get_brief(brief.id) is not None

                # 3. Generate cold outreach draft
                draft = service.generate_draft(prof.id, brief.id, student_name="John Doe", persist=True)
                assert isinstance(draft, EmailDraft)
                assert draft.status == EmailDraftStatus.DRAFT_PENDING
                assert draft.recipient_email == "lamport@stanford.edu"
                assert "John Doe" in draft.body
                assert repo.get_draft(draft.id) is not None

    def test_match_and_draft_pipeline_mocked_offline(
        self,
        tmp_path: Path,
        sample_resume_file: Path,
    ) -> None:
        directory_html = """
        <html>
        <head><title>Faculty | Stanford CS</title></head>
        <body>
            <div class="faculty-card">
                <h3><a href="/faculty/lamport">Dr. Leslie Lamport</a></h3>
                <p>Professor of Computer Science</p>
                <p><a href="mailto:lamport@stanford.edu">lamport@stanford.edu</a></p>
                <p>Research: Distributed Systems, Formal Methods</p>
            </div>
        </body>
        </html>
        """
        openalex_json = {
            "results": [
                {
                    "id": "https://openalex.org/W101",
                    "title": "Fast Paxos Protocol",
                    "doi": "https://doi.org/10.1145/101.102",
                    "publication_year": 2024,
                    "cited_by_count": 100,
                    "abstract_inverted_index": {"State": [0], "machine": [1], "replication.": [2]},
                    "authorships": [
                        {
                            "author": {"id": "A1", "display_name": "Leslie Lamport"},
                            "institutions": [{"id": "I1", "display_name": "Stanford University"}],
                            "raw_affiliation_strings": ["Stanford University"],
                        }
                    ],
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            url_s = str(request.url)
            if "api.openalex.org" in url_s:
                return httpx.Response(200, json=openalex_json)
            elif "export.arxiv.org" in url_s:
                return httpx.Response(200, text="<feed></feed>")
            return httpx.Response(200, text=directory_html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with ArtemisRepository(":memory:") as repo:
            with ArtemisScoutingService(repository=repo, http_client=http_client, llm_provider=MockLLMProvider()) as service:
                dossiers = service.match_and_draft_pipeline(
                    directory_url="https://cs.stanford.edu/faculty",
                    resume_path=sample_resume_file,
                    keywords=["distributed"],
                    max_faculty=1,
                    max_papers_per_faculty=1,
                    student_name="John Doe",
                    persist=True,
                )

                assert len(dossiers) == 1
                prof, paper, brief, draft = dossiers[0]
                assert prof.name == "Leslie Lamport"
                assert "Fast Paxos Protocol" in paper.title
                assert isinstance(brief, ResearchBrief)
                assert isinstance(draft, EmailDraft)
                assert draft.status == EmailDraftStatus.DRAFT_PENDING


class TestMilestone3CLI:
    def test_cli_ingest_resume(self, sample_resume_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        db_file = tmp_path / "test_cli.db"
        exit_code = main(["ingest-resume", str(sample_resume_file), "--db", str(db_file)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "A.R.T.E.M.I.S. RÉSUMÉ EVIDENCE INGESTION REPORT" in captured.out
        assert "Raft" in captured.out
        assert "UNVERIFIED" in captured.out

    def test_cli_brief_and_draft_commands(
        self,
        sample_resume_file: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        db_file = tmp_path / "test_cli2.db"
        # 1. Ingest resume
        main(["ingest-resume", str(sample_resume_file), "--db", str(db_file)])

        # 2. Add professor and paper to db
        with ArtemisRepository(db_file) as repo:
            prof = repo.create_professor(
                Professor(
                    name="Prof. Alice",
                    institution="Test University",
                    email="alice@test.edu",
                    email_status=VerificationStatus.VERIFIED,
                )
            )
            paper = repo.create_paper(
                Paper(
                    title="Byzantine Consensus in Sparse Networks",
                    abstract="Analyzing quorum systems under partition.",
                )
            )
            prof_id = prof.id
            paper_id = paper.id

        # 3. Test brief CLI
        exit_code_brief = main(["brief", "--prof", prof_id, "--paper", paper_id, "--db", str(db_file)])
        assert exit_code_brief == 0
        captured = capsys.readouterr()
        assert "A.R.T.E.M.I.S. RESEARCH BRIEF" in captured.out
        assert "Byzantine Consensus" in captured.out

        # Retrieve created brief ID
        with ArtemisRepository(db_file) as repo:
            briefs = repo.list_briefs_by_professor(prof_id)
            assert len(briefs) == 1
            brief_id = briefs[0].id

        # 4. Test draft CLI
        exit_code_draft = main(["draft", "--prof", prof_id, "--brief", brief_id, "--name", "Bob", "--db", str(db_file)])
        assert exit_code_draft == 0
        captured_draft = capsys.readouterr()
        assert "A.R.T.E.M.I.S. OUTREACH EMAIL DRAFT" in captured_draft.out
        assert "alice@test.edu" in captured_draft.out
        assert "Bob" in captured_draft.out
