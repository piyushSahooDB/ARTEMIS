"""Unit tests for the ARTEMIS CLI interface."""

from __future__ import annotations

import pytest

from artemis.cli import format_table, main, parse_args
from artemis.crawler.exceptions import JavaScriptRenderedPageError
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.scouting.models import AuthorMatch, ScoutedPaper
from artemis.service import FacultyScoutResult


class TestCLI:
    def test_parse_args_defaults(self) -> None:
        args = parse_args(["scout", "https://cs.cmu.edu/faculty"])
        assert args.command == "scout"
        assert args.url == "https://cs.cmu.edu/faculty"
        assert args.max_faculty == 5
        assert args.max_papers == 3
        assert args.db == "artemis.db"
        assert args.no_persist is False

    def test_parse_args_custom_options(self) -> None:
        args = parse_args([
            "scout",
            "-u", "https://cs.stanford.edu/faculty",
            "-k", "distributed", "systems",
            "-f", "10",
            "-p", "4",
            "--db", "test.db",
            "--no-persist",
        ])
        assert args.url == "https://cs.stanford.edu/faculty"
        assert args.keywords == ["distributed", "systems"]
        assert args.max_faculty == 10
        assert args.max_papers == 4
        assert args.db == "test.db"
        assert args.no_persist is True

    def test_format_table_renders_ranked_output(self) -> None:
        prof = Professor(
            name="Dr. Leslie Lamport",
            title="Principal Researcher",
            institution="Stanford University",
            email="lamport@example.edu",
            email_status=VerificationStatus.VERIFIED,
            profile_url="https://example.edu/~lamport",
            research_interests=["Distributed Systems", "Temporal Logic"],
        )
        paper = Paper(
            title="Time, Clocks, and the Ordering of Events in a Distributed System",
            year=1978,
            venue="Communications of the ACM",
            doi="10.1145/359545.359563",
            citation_count=14000,
            sources=[SourceProvenance(source_url="https://doi.org/10.1145/359545.359563", source_name="crossref")],
        )
        match = AuthorMatch(
            author_name="Leslie Lamport",
            is_institution_matched=True,
            confidence=1.0,
            status=VerificationStatus.VERIFIED,
            notes="Institutional affiliation verified.",
        )
        scouted_paper = ScoutedPaper(
            paper=paper,
            relevance_score=0.9,
            recency_score=0.3,
            citation_score=1.0,
            composite_relevance=0.85,
            author_match=match,
            matched_keywords=["distributed"],
        )

        res = FacultyScoutResult(professor=prof, papers=[scouted_paper])
        output = format_table([res])

        assert "Leslie Lamport" in output
        assert "Stanford University" in output
        assert "Time, Clocks" in output
        assert "14000" in output
        assert "AFFILIATION MATCHED IN METADATA" in output
        assert "https://doi.org/10.1145/359545.359563" in output

    def test_main_missing_command_returns_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main([])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Usage: artemis scout" in captured.out

    def test_main_spa_error_reports_clearly(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def mock_scout(*args: object, **kwargs: object) -> list[FacultyScoutResult]:
            raise JavaScriptRenderedPageError("https://spa.university.edu")

        monkeypatch.setattr(
            "artemis.service.ArtemisScoutingService.scout",
            mock_scout,
        )

        exit_code = main(["scout", "https://spa.university.edu"])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "JavaScript-Rendered Directory Detected" in captured.out
        assert "client-side JavaScript (SPA)" in captured.out

    def test_main_successful_execution(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        prof = Professor(name="Dr. Shannon", institution="MIT")
        mock_result = [FacultyScoutResult(professor=prof, papers=[])]

        monkeypatch.setattr(
            "artemis.service.ArtemisScoutingService.scout",
            lambda *args, **kwargs: mock_result,
        )

        exit_code = main(["scout", "https://mit.edu/faculty", "--no-persist"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Dr. Shannon" in captured.out
        assert "MIT" in captured.out
