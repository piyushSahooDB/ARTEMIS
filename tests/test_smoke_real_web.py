"""Integration smoke test for manual verification against real university pages."""

from __future__ import annotations

import os
import sys

import pytest

from artemis.service import ArtemisScoutingService

# Stable server-rendered directory for manual smoke testing:
# e.g., Princeton Computer Science Faculty directory or University of Oxford CS
DEFAULT_TEST_DIRECTORY_URL = "https://www.cs.princeton.edu/people/faculty"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Requires live network access. Run with RUN_LIVE_TESTS=1 to execute.",
)
def test_live_faculty_and_paper_scouting() -> None:
    """Live smoke test verifying faculty discovery and paper scouting against a real page."""
    url = os.environ.get("ARTEMIS_TEST_URL", DEFAULT_TEST_DIRECTORY_URL)
    keywords = ["systems", "machine learning"]

    with ArtemisScoutingService(db_path=":memory:") as service:
        results = service.scout(
            directory_url=url,
            keywords=keywords,
            max_faculty=2,
            max_papers_per_faculty=2,
            persist=True,
        )

    assert len(results) > 0, f"Expected at least 1 faculty member from {url}"
    prof = results[0].professor
    assert prof.name, "Discovered professor must have a name"
    assert prof.institution, "Discovered professor must have an institution"
    assert len(prof.sources) > 0, "Professor must have source provenance"

    # If papers were discovered, ensure they carry source links
    if results[0].papers:
        top_paper = results[0].papers[0].paper
        assert top_paper.title, "Paper must have a title"
        assert len(top_paper.sources) > 0, "Paper must have source provenance"


def run_manual_smoke(target_url: str | None = None) -> int:
    """Manual execution helper for testing directly from terminal."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    url = target_url or DEFAULT_TEST_DIRECTORY_URL
    print(f"\n[+] Running manual integration smoke test against: {url}")
    print("    Keywords: ['distributed', 'systems']")

    try:
        with ArtemisScoutingService(db_path=":memory:") as service:
            results = service.scout(
                directory_url=url,
                keywords=["distributed", "systems"],
                max_faculty=3,
                max_papers_per_faculty=2,
                persist=True,
            )

        print(f"\n[OK] Successfully discovered {len(results)} faculty members.")
        for i, res in enumerate(results, 1):
            prof = res.professor
            print(f"\n[{i}] {prof.name} ({prof.institution})")
            print(f"    Title: {prof.title} | Email: {prof.email or 'N/A'}")
            print(f"    Profile: {prof.profile_url}")
            print(f"    Interests: {', '.join(prof.research_interests[:4])}")
            print(f"    Papers Found: {len(res.papers)}")
            for sp in res.papers:
                print(f"      - \"{sp.paper.title}\" ({sp.paper.year})")
                print(f"        Composite Rel: {sp.composite_relevance:.2f} | Author Confidence: {sp.author_match.confidence:.2f}")
                print(f"        Source: {sp.paper.sources[0].source_url if sp.paper.sources else 'N/A'}")

        print("\n[OK] Smoke test completed successfully.")
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Smoke test encountered error: {exc}")
        return 1


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_manual_smoke(test_url))
