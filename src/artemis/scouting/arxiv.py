"""arXiv academic API client for preprints and publication discovery."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote_plus

from artemis.crawler.client import PoliteHttpClient
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.scouting.models import AuthorMatch

ARXIV_API_URL = "https://export.arxiv.org/api/query"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def clean_arxiv_id(raw_id: str) -> str:
    """Extract standard arXiv identifier (e.g. '2301.12345') from arXiv URI."""
    m = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", raw_id)
    if m:
        return m.group(1)
    # Support older identifiers e.g. hep-th/9901001
    parts = raw_id.split("/abs/")
    if len(parts) > 1:
        return parts[1].split("v")[0]
    return raw_id.strip()


class ArxivClient:
    """Client for querying the arXiv preprint repository via its Atom API."""

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self.client = client or PoliteHttpClient()

    def search_papers(
        self,
        author_name: str,
        institution: str | None = None,
        keywords: list[str] | None = None,
        max_results: int = 10,
    ) -> list[tuple[Paper, AuthorMatch]]:
        """Search arXiv by author name and optional keywords."""
        # Clean author name for query
        cleaned_author = author_name.replace('"', "").strip()
        query = f'au:"{cleaned_author}"'
        if keywords:
            kw_terms = " AND ".join(f'all:"{kw.replace(chr(34), "").strip()}"' for kw in keywords if kw.strip())
            if kw_terms:
                query = f"({query}) AND ({kw_terms})"

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        response = self.client.get(ARXIV_API_URL, params=params)
        return self._parse_feed(response.text, author_name, institution)

    def _parse_feed(
        self,
        xml_text: str,
        target_author: str,
        target_institution: str | None,
    ) -> list[tuple[Paper, AuthorMatch]]:
        """Parse Atom XML response into Paper instances."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        entries = root.findall("atom:entry", ATOM_NS)
        results: list[tuple[Paper, AuthorMatch]] = []

        for entry in entries:
            # Check for dummy error entry
            id_tag = entry.find("atom:id", ATOM_NS)
            if id_tag is None or not id_tag.text:
                continue

            raw_id = id_tag.text.strip()
            arxiv_id = clean_arxiv_id(raw_id)

            title_tag = entry.find("atom:title", ATOM_NS)
            title = " ".join(title_tag.text.split()) if (title_tag is not None and title_tag.text) else "Untitled"

            summary_tag = entry.find("atom:summary", ATOM_NS)
            abstract = " ".join(summary_tag.text.split()) if (summary_tag is not None and summary_tag.text) else None

            pub_tag = entry.find("atom:published", ATOM_NS)
            pub_date: str | None = None
            year: int | None = None
            if pub_tag is not None and pub_tag.text:
                pub_date = pub_tag.text[:10]
                try:
                    year = int(pub_date[:4])
                except (ValueError, TypeError):
                    pass

            doi_tag = entry.find("arxiv:doi", ATOM_NS)
            doi = doi_tag.text.strip() if (doi_tag is not None and doi_tag.text) else None

            venue_tag = entry.find("arxiv:journal_ref", ATOM_NS)
            venue = venue_tag.text.strip() if (venue_tag is not None and venue_tag.text) else "arXiv"

            # Links
            landing_url = f"https://arxiv.org/abs/{arxiv_id}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            for link in entry.findall("atom:link", ATOM_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                elif link.get("rel") == "alternate":
                    landing_url = link.get("href") or landing_url

            # Authors & Affiliations
            author_names: list[str] = []
            affiliations: list[str] = []
            target_norm = target_author.lower()

            for author_elem in entry.findall("atom:author", ATOM_NS):
                name_elem = author_elem.find("atom:name", ATOM_NS)
                if name_elem is not None and name_elem.text:
                    author_name_str = name_elem.text.strip()
                    author_names.append(author_name_str)

                    if target_norm in author_name_str.lower():
                        affil_elem = author_elem.find("arxiv:affiliation", ATOM_NS)
                        if affil_elem is not None and affil_elem.text:
                            affiliations.append(affil_elem.text.strip())

            # Check institutional affiliation
            is_inst_matched = False
            if target_institution and affiliations:
                clean_target = target_institution.lower().replace("university", "").strip()
                is_inst_matched = any(clean_target in aff.lower() for aff in affiliations)

            if is_inst_matched:
                author_match = AuthorMatch(
                    author_name=target_author,
                    affiliations=affiliations,
                    is_institution_matched=True,
                    confidence=1.0,
                    status=VerificationStatus.VERIFIED,
                    notes=f"Author institutional affiliation verified with {target_institution} on arXiv.",
                )
            else:
                author_match = AuthorMatch(
                    author_name=target_author,
                    affiliations=affiliations,
                    is_institution_matched=False,
                    confidence=0.4,
                    status=VerificationStatus.UNVERIFIED,
                    notes="Name-only match; institutional affiliation not verified in metadata.",
                )

            prov = SourceProvenance(
                source_url=landing_url,
                source_name="arxiv",
                snippet=f"Retrieved from arXiv:{arxiv_id} - {title}",
                verification_status=author_match.status,
            )

            paper = Paper(
                title=title,
                abstract=abstract,
                published_date=pub_date,
                year=year,
                venue=venue,
                doi=doi,
                arxiv_id=arxiv_id,
                url=landing_url,
                pdf_url=pdf_url,
                citation_count=None,
                author_names=author_names,
                sources=[prov],
            )

            results.append((paper, author_match))

        return results
