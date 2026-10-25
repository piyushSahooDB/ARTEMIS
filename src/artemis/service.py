"""Scouting service orchestrating faculty directory discovery and paper scouting."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Union

from artemis.brief.synthesizer import ResearchBriefSynthesizer
from artemis.crawler.client import PoliteHttpClient
from artemis.crawler.faculty_parser import FacultyDirectoryParser
from artemis.db.repository import ArtemisRepository
from artemis.email.generator import DraftGenerator
from artemis.llm.provider import LLMProvider, get_llm_provider
from artemis.models.brief import ResearchBrief
from artemis.models.email import EmailDraft
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import ResumeEvidence
from artemis.resume.extractor import ResumeParser
from artemis.scouting.arxiv import ArxivClient
from artemis.scouting.crossref import CrossrefClient
from artemis.scouting.deduplication import deduplicate_papers
from artemis.scouting.models import AuthorMatch, ScoutedPaper
from artemis.scouting.openalex import OpenAlexClient
from artemis.scouting.ranker import PaperRanker

logger = logging.getLogger(__name__)


@dataclass
class FacultyScoutResult:
    """Consolidated scouting result for a discovered faculty member."""

    professor: Professor
    papers: list[ScoutedPaper] = field(default_factory=list)

    @property
    def best_paper(self) -> ScoutedPaper | None:
        """Return the highest ranked paper if any exist."""
        return self.papers[0] if self.papers else None


class ArtemisScoutingService:
    """High-level service coordinating faculty exploration, paper discovery, and persistence."""

    def __init__(
        self,
        repository: ArtemisRepository | None = None,
        db_path: Union[str, Path] = "artemis.db",
        http_client: PoliteHttpClient | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.http_client = http_client or PoliteHttpClient()
        self.parser = FacultyDirectoryParser(client=self.http_client)
        self.openalex = OpenAlexClient(client=self.http_client)
        self.arxiv = ArxivClient(client=self.http_client)
        self.crossref = CrossrefClient(client=self.http_client)
        self.ranker = PaperRanker()
        self.resume_parser = ResumeParser()
        self.llm = llm_provider or get_llm_provider()
        self.brief_synthesizer = ResearchBriefSynthesizer(llm_provider=self.llm)
        self.draft_generator = DraftGenerator(llm_provider=self.llm)

        self._repo = repository
        self._db_path = db_path
        self._owns_repo = repository is None

    def get_repository(self) -> ArtemisRepository:
        """Get or initialize the repository."""
        if self._repo is None:
            self._repo = ArtemisRepository(self._db_path)
        return self._repo

    def close(self) -> None:
        """Clean up resources."""
        self.http_client.close()
        if self._owns_repo and self._repo:
            self._repo.close()

    def __enter__(self) -> ArtemisScoutingService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def scout(
        self,
        directory_url: str,
        keywords: Sequence[str] | None = None,
        max_faculty: int = 5,
        max_papers_per_faculty: int = 3,
        institution: str | None = None,
        persist: bool = True,
    ) -> list[FacultyScoutResult]:
        """Scout a faculty directory URL and find top matching research publications."""
        kw_list = list(keywords) if keywords else []

        # 1. Discover faculty
        professors = self.parser.parse_directory(
            directory_url=directory_url,
            research_keywords=kw_list,
            max_faculty=max_faculty,
            max_profile_depth=max_faculty,
            institution_name=institution,
        )

        results: list[FacultyScoutResult] = []
        repo = self.get_repository() if persist else None

        # 2. Scout academic papers for each faculty member
        for prof in professors:
            scouted_papers = self._scout_papers_for_professor(
                professor=prof,
                keywords=kw_list,
                max_papers=max_papers_per_faculty,
            )

            # 3. Optional persistence to existing SQLite ArtemisRepository
            if repo:
                try:
                    self._persist_professor_and_papers(repo, prof, [sp.paper for sp in scouted_papers])
                except Exception as exc:
                    logger.warning(f"Could not persist results for {prof.name}: {exc}")

            results.append(FacultyScoutResult(professor=prof, papers=scouted_papers))

        return results

    def _scout_papers_for_professor(
        self,
        professor: Professor,
        keywords: list[str],
        max_papers: int,
    ) -> list[ScoutedPaper]:
        """Query OpenAlex, arXiv, deduplicate, enrich with Crossref, and rank."""
        raw_candidates: list[tuple[Paper, AuthorMatch]] = []

        # Query OpenAlex
        try:
            oa_results = self.openalex.search_papers(
                author_name=professor.name,
                institution=professor.institution,
                keywords=keywords,
                max_results=max_papers * 3,
            )
            raw_candidates.extend(oa_results)
        except Exception as exc:
            logger.warning(f"OpenAlex query failed for {professor.name}: {exc}")

        # Query arXiv
        try:
            arxiv_results = self.arxiv.search_papers(
                author_name=professor.name,
                institution=professor.institution,
                keywords=keywords,
                max_results=max_papers * 2,
            )
            raw_candidates.extend(arxiv_results)
        except Exception as exc:
            logger.warning(f"arXiv query failed for {professor.name}: {exc}")

        # Deduplicate
        deduped = deduplicate_papers(raw_candidates)

        # Crossref enrichment for top candidates with DOIs
        enriched: list[tuple[Paper, AuthorMatch]] = []
        for paper, author_match in deduped:
            if paper.doi and (not paper.venue or not author_match.is_institution_matched):
                try:
                    paper, match_update = self.crossref.enrich_paper(
                        paper=paper,
                        target_author=professor.name,
                        target_institution=professor.institution,
                    )
                    if match_update:
                        author_match = match_update
                except Exception:
                    pass
            enriched.append((paper, author_match))

        # Rank
        ranked = self.ranker.rank(enriched, keywords=keywords)
        return ranked[:max_papers]

    def _persist_professor_and_papers(
        self,
        repo: ArtemisRepository,
        professor: Professor,
        papers: Sequence[Paper],
    ) -> None:
        """Persist professor and associated papers in SQLite repository with deduplication."""
        # 1. Check if professor already exists (by email or name + institution)
        existing_prof = None
        if professor.email:
            existing_prof = repo.find_professor_by_email(professor.email)
        if not existing_prof:
            existing_prof = repo.find_professor_by_name(professor.name, professor.institution)

        if existing_prof:
            professor.id = existing_prof.id
            professor.created_at = existing_prof.created_at
            repo.update_professor(professor)
            prof_id = existing_prof.id
        else:
            repo.create_professor(professor)
            prof_id = professor.id

        # 2. Check papers and link
        for paper in papers:
            existing_paper = None
            if paper.doi:
                existing_paper = repo.find_paper_by_doi(paper.doi)
            if not existing_paper and paper.arxiv_id:
                existing_paper = repo.find_paper_by_arxiv_id(paper.arxiv_id)
            if not existing_paper and paper.title:
                existing_paper = repo.find_paper_by_title(paper.title)

            if existing_paper:
                paper.id = existing_paper.id
                paper.created_at = existing_paper.created_at
                repo.update_paper(paper)
                paper_id = existing_paper.id
            else:
                repo.create_paper(paper)
                paper_id = paper.id

            repo.link_professor_paper(prof_id, paper_id, relationship_type="author")

    # -------------------------------------------------------------------------
    # Milestone 3: Résumé Ingestion, Brief Synthesis, and Email Drafting
    # -------------------------------------------------------------------------

    def ingest_resume(
        self,
        file_path: Union[str, Path],
        persist: bool = True,
    ) -> list[ResumeEvidence]:
        """Ingest student résumé (.pdf, .txt, .md), extracting structured unverified evidence."""
        evidence_items = self.resume_parser.parse_file(file_path)
        if persist:
            repo = self.get_repository()
            persisted_items: list[ResumeEvidence] = []
            for ev in evidence_items:
                existing = repo.find_evidence_by_title(ev.title)
                if existing:
                    ev.id = existing.id
                    ev.created_at = existing.created_at
                    repo.update_evidence(ev)
                    persisted_items.append(ev)
                else:
                    repo.create_evidence(ev)
                    persisted_items.append(ev)
            return persisted_items
        return evidence_items

    def synthesize_brief(
        self,
        professor_id: str,
        paper_id: str,
        evidence_ids: Sequence[str] | None = None,
        persist: bool = True,
    ) -> ResearchBrief:
        """Synthesize a research brief connecting a professor's paper to student evidence."""
        repo = self.get_repository()
        professor = repo.get_professor(professor_id)
        if not professor:
            raise KeyError(f"Professor with ID '{professor_id}' not found in repository.")

        paper = repo.get_paper(paper_id)
        if not paper:
            raise KeyError(f"Paper with ID '{paper_id}' not found in repository.")

        if evidence_ids:
            evidence = [repo.get_evidence(eid) for eid in evidence_ids if repo.get_evidence(eid)]
        else:
            evidence = repo.list_evidence()

        brief = self.brief_synthesizer.synthesize(
            professor=professor,
            paper=paper,
            evidence=evidence,
        )

        if persist:
            repo.create_brief(brief)

        return brief

    def generate_draft(
        self,
        professor_id: str,
        brief_id: str,
        student_name: str = "Student Researcher",
        persist: bool = True,
    ) -> EmailDraft:
        """Generate a personalized, grounded cold outreach draft from an existing brief."""
        repo = self.get_repository()
        professor = repo.get_professor(professor_id)
        if not professor:
            raise KeyError(f"Professor with ID '{professor_id}' not found in repository.")

        brief = repo.get_brief(brief_id)
        if not brief:
            raise KeyError(f"Research brief with ID '{brief_id}' not found in repository.")

        paper = repo.get_paper(brief.paper_id) if brief.paper_id else None
        if not paper:
            # Fallback to creating a stub paper from brief headline
            paper = Paper(title=brief.headline.replace("[Abstract-Based Brief] ", ""))

        # Retrieve matched evidence items
        evidence = repo.list_evidence()

        draft = self.draft_generator.generate_draft(
            professor=professor,
            brief=brief,
            paper=paper,
            evidence=evidence,
            student_name=student_name,
        )

        if persist:
            repo.create_draft(draft)

        return draft

    def match_and_draft_pipeline(
        self,
        directory_url: str,
        resume_path: Union[str, Path],
        keywords: Sequence[str] | None = None,
        max_faculty: int = 3,
        max_papers_per_faculty: int = 1,
        student_name: str = "Student Researcher",
        institution: str | None = None,
        persist: bool = True,
    ) -> list[tuple[Professor, Paper, ResearchBrief, EmailDraft]]:
        """End-to-end pipeline: scout directory -> ingest résumé -> synthesize brief -> generate draft."""
        # 1. Ingest student résumé
        evidence = self.ingest_resume(file_path=resume_path, persist=persist)

        # 2. Scout faculty & papers
        scout_results = self.scout(
            directory_url=directory_url,
            keywords=keywords,
            max_faculty=max_faculty,
            max_papers_per_faculty=max_papers_per_faculty,
            institution=institution,
            persist=persist,
        )

        pipeline_outputs: list[tuple[Professor, Paper, ResearchBrief, EmailDraft]] = []
        repo = self.get_repository() if persist else None

        # 3. For each scouted faculty, synthesize brief and generate draft on best matching paper
        for res in scout_results:
            prof = res.professor
            best_paper_scouted = res.best_paper
            if not best_paper_scouted:
                continue

            paper = best_paper_scouted.paper

            # Synthesize brief
            brief = self.brief_synthesizer.synthesize(
                professor=prof,
                paper=paper,
                evidence=evidence,
            )
            if repo:
                repo.create_brief(brief)

            # Generate draft
            draft = self.draft_generator.generate_draft(
                professor=prof,
                brief=brief,
                paper=paper,
                evidence=evidence,
                student_name=student_name,
            )
            if repo:
                repo.create_draft(draft)

            pipeline_outputs.append((prof, paper, brief, draft))

        return pipeline_outputs
