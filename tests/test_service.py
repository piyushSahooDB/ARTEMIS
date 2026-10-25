"""Unit tests for the ArtemisScoutingService coordinator."""

from __future__ import annotations

import httpx

from artemis.crawler.client import PoliteHttpClient
from artemis.db.repository import ArtemisRepository
from artemis.service import ArtemisScoutingService


class TestArtemisScoutingService:
    def test_end_to_end_scouting_and_persistence(self) -> None:
        directory_html = """
        <html>
        <head><title>Faculty | Stanford Computer Science</title></head>
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
                    "id": "https://openalex.org/W100",
                    "title": "The Part-Time Parliament (Paxos)",
                    "doi": "https://doi.org/10.1145/279227.279229",
                    "publication_year": 1998,
                    "cited_by_count": 6500,
                    "abstract_inverted_index": {"Recent": [0], "archaeological": [1], "discoveries.": [2]},
                    "authorships": [
                        {
                            "author": {"id": "A10", "display_name": "Leslie Lamport"},
                            "institutions": [{"id": "I10", "display_name": "Stanford University"}],
                            "raw_affiliation_strings": ["Stanford University"],
                        }
                    ],
                }
            ]
        }

        arxiv_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry>
            <id>http://arxiv.org/abs/2301.00001v1</id>
            <title>Specifying Systems with TLA+</title>
            <summary>A guide to formal system specification.</summary>
            <published>2023-01-10T12:00:00Z</published>
            <author>
              <name>Leslie Lamport</name>
              <arxiv:affiliation>Stanford University</arxiv:affiliation>
            </author>
          </entry>
        </feed>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "api.openalex.org" in url_str:
                return httpx.Response(200, json=openalex_json)
            elif "export.arxiv.org" in url_str:
                return httpx.Response(200, text=arxiv_xml)
            elif "api.crossref.org" in url_str:
                return httpx.Response(404, json={})
            return httpx.Response(200, text=directory_html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with ArtemisRepository(":memory:") as repo:
            with ArtemisScoutingService(repository=repo, http_client=http_client) as service:
                results = service.scout(
                    directory_url="https://cs.stanford.edu/faculty",
                    keywords=["distributed", "paxos"],
                    max_faculty=2,
                    max_papers_per_faculty=2,
                    persist=True,
                )

                assert len(results) == 1
                res = results[0]
                prof = res.professor
                assert prof.name == "Leslie Lamport"
                assert len(res.papers) == 2

                # Verify SQLite database persistence
                persisted_prof = repo.get_professor(prof.id)
                assert persisted_prof is not None
                assert persisted_prof.name == "Leslie Lamport"

                linked_papers = repo.get_papers_by_professor(prof.id)
                assert len(linked_papers) == 2
                paper_titles = [p.title for p in linked_papers]
                assert "The Part-Time Parliament (Paxos)" in paper_titles
                assert "Specifying Systems with TLA+" in paper_titles

                # Test idempotency: re-running scouting must not create duplicate records
                service.scout(
                    directory_url="https://cs.stanford.edu/faculty",
                    keywords=["distributed", "paxos"],
                    max_faculty=2,
                    max_papers_per_faculty=2,
                    persist=True,
                )
                assert len(repo.list_professors()) == 1
                assert len(repo.list_papers()) == 2
                assert len(repo.get_papers_by_professor(prof.id)) == 2
