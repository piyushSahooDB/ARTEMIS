"""Unit tests for academic paper discovery, deduplication, and ranking."""

from __future__ import annotations

import httpx
import pytest

from artemis.crawler.client import PoliteHttpClient
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.scouting.arxiv import ArxivClient
from artemis.scouting.crossref import CrossrefClient
from artemis.scouting.deduplication import deduplicate_papers
from artemis.scouting.models import AuthorMatch
from artemis.scouting.openalex import OpenAlexClient, reconstruct_abstract
from artemis.scouting.ranker import PaperRanker


class TestOpenAlexClient:
    def test_reconstruct_abstract(self) -> None:
        inverted = {"We": [0], "study": [1], "distributed": [2], "systems.": [3]}
        assert reconstruct_abstract(inverted) == "We study distributed systems."
        assert reconstruct_abstract(None) is None
        assert reconstruct_abstract({}) is None

    def test_search_papers_with_verified_institution(self) -> None:
        mock_payload = {
            "results": [
                {
                    "id": "https://openalex.org/W123456789",
                    "title": "Scalable Consensus in Geo-Distributed Environments",
                    "doi": "https://doi.org/10.1145/12345.67890",
                    "publication_year": 2024,
                    "publication_date": "2024-04-12",
                    "cited_by_count": 25,
                    "primary_location": {
                        "landing_page_url": "https://doi.org/10.1145/12345.67890",
                        "pdf_url": "https://example.edu/paper.pdf",
                        "source": {"display_name": "ACM SIGCOMM 2024"},
                    },
                    "abstract_inverted_index": {"State": [0], "machine": [1], "replication.": [2]},
                    "authorships": [
                        {
                            "author": {"id": "A1", "display_name": "John Doe"},
                            "institutions": [{"id": "I1", "display_name": "Stanford University"}],
                            "raw_affiliation_strings": ["Department of Computer Science, Stanford University"],
                        }
                    ],
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_payload)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        oa = OpenAlexClient(client=http_client)

        results = oa.search_papers(
            author_name="John Doe",
            institution="Stanford University",
            keywords=["consensus"],
        )

        assert len(results) == 1
        paper, match = results[0]
        assert paper.title == "Scalable Consensus in Geo-Distributed Environments"
        assert paper.doi == "10.1145/12345.67890"
        assert paper.abstract == "State machine replication."
        assert paper.venue == "ACM SIGCOMM 2024"
        assert paper.year == 2024
        assert paper.citation_count == 25

        # Verification check
        assert match.is_institution_matched is True
        assert match.confidence == 1.0
        assert match.status == VerificationStatus.VERIFIED
        assert "Stanford" in match.notes
        http_client.close()

    def test_search_papers_ambiguous_author_name_only_match(self) -> None:
        mock_payload = {
            "results": [
                {
                    "id": "https://openalex.org/W999",
                    "title": "Quantum Error Correction",
                    "publication_year": 2023,
                    "authorships": [
                        {
                            "author": {"id": "A2", "display_name": "John Doe"},
                            "institutions": [{"id": "I2", "display_name": "University of Tokyo"}],
                            "raw_affiliation_strings": ["Tokyo, Japan"],
                        }
                    ],
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_payload)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        oa = OpenAlexClient(client=http_client)

        results = oa.search_papers(
            author_name="John Doe",
            institution="Stanford University",
        )

        assert len(results) == 1
        _, match = results[0]
        # Must be marked uncertain because Tokyo != Stanford
        assert match.is_institution_matched is False
        assert match.confidence == 0.4
        assert match.status == VerificationStatus.UNVERIFIED
        http_client.close()


class TestArxivClient:
    def test_parse_arxiv_feed(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry>
            <id>http://arxiv.org/abs/2401.99999v1</id>
            <title>Fast Paxos with Speculative Execution</title>
            <summary>We present a variant of Paxos for wide-area networks.</summary>
            <published>2024-01-20T12:00:00Z</published>
            <arxiv:doi>10.1145/99999.88888</arxiv:doi>
            <arxiv:journal_ref>IEEE TPDS 2024</arxiv:journal_ref>
            <link title="pdf" href="https://arxiv.org/pdf/2401.99999.pdf" />
            <author>
              <name>John Doe</name>
              <arxiv:affiliation>Stanford University</arxiv:affiliation>
            </author>
          </entry>
        </feed>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=xml)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        client = ArxivClient(client=http_client)

        results = client.search_papers("John Doe", institution="Stanford University")
        assert len(results) == 1
        paper, match = results[0]
        assert paper.arxiv_id == "2401.99999"
        assert paper.title == "Fast Paxos with Speculative Execution"
        assert paper.year == 2024
        assert paper.venue == "IEEE TPDS 2024"
        assert paper.doi == "10.1145/99999.88888"
        assert match.is_institution_matched is True
        assert match.status == VerificationStatus.VERIFIED
        http_client.close()

    def test_malformed_xml_returns_empty_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<broken-xml><<<")

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        client = ArxivClient(client=http_client)
        results = client.search_papers("John Doe")
        assert results == []
        http_client.close()


class TestCrossrefClient:
    def test_resolve_and_enrich_doi(self) -> None:
        msg = {
            "container-title": ["Journal of Systems Architecture"],
            "published-print": {"date-parts": [[2023, 5, 10]]},
            "author": [
                {
                    "given": "John",
                    "family": "Doe",
                    "affiliation": [{"name": "Stanford University"}],
                }
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"message": msg})

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        crossref = CrossrefClient(client=http_client)

        paper = Paper(
            title="Consensus Benchmarks",
            doi="10.1016/j.sysarc.2023.01",
        )

        enriched, match = crossref.enrich_paper(paper, "John Doe", "Stanford University")
        assert enriched.venue == "Journal of Systems Architecture"
        assert enriched.year == 2023
        assert match is not None
        assert match.is_institution_matched is True
        assert match.status == VerificationStatus.VERIFIED
        http_client.close()


class TestDeduplication:
    def test_deduplicate_by_doi(self) -> None:
        p1 = Paper(
            title="Consensus Protocols",
            doi="10.1145/12345.67890",
            citation_count=10,
            abstract="Short summary",
            sources=[SourceProvenance(source_url="https://openalex.org/w1", source_name="openalex")],
        )
        m1 = AuthorMatch(author_name="John Doe", confidence=0.4)

        p2 = Paper(
            title="Consensus Protocols",
            doi="10.1145/12345.67890",
            arxiv_id="2401.12345",
            citation_count=25,
            abstract="Much more comprehensive abstract describing Paxos and Raft.",
            sources=[SourceProvenance(source_url="https://arxiv.org/abs/2401.12345", source_name="arxiv")],
        )
        m2 = AuthorMatch(author_name="John Doe", confidence=1.0, is_institution_matched=True, status=VerificationStatus.VERIFIED)

        deduped = deduplicate_papers([(p1, m1), (p2, m2)])
        assert len(deduped) == 1

        merged_paper, merged_match = deduped[0]
        assert merged_paper.doi == "10.1145/12345.67890"
        assert merged_paper.arxiv_id == "2401.12345"
        assert merged_paper.citation_count == 25
        assert "Much more comprehensive" in merged_paper.abstract
        assert len(merged_paper.sources) == 2
        assert merged_match.is_institution_matched is True
        assert merged_match.confidence == 1.0

    def test_deduplicate_by_normalized_title(self) -> None:
        p1 = Paper(title="High-Throughput State Machine Replication in Datacenters", year=2024)
        m1 = AuthorMatch(author_name="John Doe")

        p2 = Paper(title="High-Throughput: State Machine Replication in Datacenters!", year=2024, arxiv_id="2402.11111")
        m2 = AuthorMatch(author_name="John Doe")

        deduped = deduplicate_papers([(p1, m1), (p2, m2)])
        assert len(deduped) == 1
        assert deduped[0][0].arxiv_id == "2402.11111"


class TestPaperRanker:
    def test_ranking_prefers_relevant_keywords(self) -> None:
        p1 = Paper(
            title="Consensus and Fault Tolerance in Distributed Key-Value Stores",
            abstract="We evaluate Paxos and Raft.",
            year=2024,
        )
        m1 = AuthorMatch(author_name="Alice", confidence=1.0, is_institution_matched=True)

        p2 = Paper(
            title="Deep Neural Networks for Image Segmentation",
            abstract="CNN architectures for medical imaging.",
            year=2024,
        )
        m2 = AuthorMatch(author_name="Alice", confidence=1.0, is_institution_matched=True)

        ranker = PaperRanker(current_year=2026)
        ranked = ranker.rank([(p2, m2), (p1, m1)], keywords=["distributed", "consensus"])

        assert len(ranked) == 2
        assert ranked[0].paper.title == p1.title
        assert ranked[0].relevance_score > ranked[1].relevance_score
        assert "distributed" in ranked[0].matched_keywords

    def test_foundational_paper_boost_protects_older_classic(self) -> None:
        # Older foundational paper with 5000 citations
        classic_paper = Paper(
            title="In Search of an Understandable Consensus Algorithm (Raft)",
            year=2014,
            citation_count=5000,
        )
        classic_match = AuthorMatch(author_name="Ongaro", confidence=1.0, is_institution_matched=True)

        # Fresh paper with 0 citations but matching keyword
        fresh_paper = Paper(
            title="A Preliminary Note on Consensus",
            year=2026,
            citation_count=0,
        )
        fresh_match = AuthorMatch(author_name="Ongaro", confidence=1.0, is_institution_matched=True)

        ranker = PaperRanker(current_year=2026)
        ranked = ranker.rank([(fresh_paper, fresh_match), (classic_paper, classic_match)], keywords=["consensus"])

        # The classic paper gets maximum citation boost (score > 0.9)
        classic_ranked = next(r for r in ranked if r.paper.title == classic_paper.title)
        fresh_ranked = next(r for r in ranked if r.paper.title == fresh_paper.title)

        assert classic_ranked.citation_score > 0.9
        assert fresh_ranked.citation_score == 0.0
        # Classic paper retains strong composite relevance (> 0.80) despite being 12 years old
        assert classic_ranked.composite_relevance > 0.80

    def test_separates_relevance_from_author_confidence(self) -> None:
        paper = Paper(title="Distributed Systems", year=2024)
        match = AuthorMatch(
            author_name="Turing",
            confidence=0.4,
            is_institution_matched=False,
            status=VerificationStatus.UNVERIFIED,
            notes="Name-only match",
        )

        ranker = PaperRanker(current_year=2026)
        ranked = ranker.rank([(paper, match)], keywords=["distributed"])

        assert len(ranked) == 1
        item = ranked[0]
        # Relevance is high based on content
        assert item.composite_relevance > 0.6
        # Author identity confidence remains strictly 0.4 unverified
        assert item.author_match.confidence == 0.4
        assert item.author_match.status == VerificationStatus.UNVERIFIED
