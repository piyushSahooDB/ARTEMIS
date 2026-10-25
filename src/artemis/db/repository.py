"""SQLite repository implementation for ARTEMIS entities."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from artemis.db.connection import get_connection
from artemis.db.schema import init_db
from artemis.models.brief import ResearchBrief
from artemis.models.common import SourceProvenance, VerificationStatus, utc_now
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


class ArtemisRepository:
    """Repository managing local-first SQLite persistence for all ARTEMIS models."""

    def __init__(self, db: Union[str, Path, sqlite3.Connection] = ":memory:") -> None:
        if isinstance(db, sqlite3.Connection):
            self.conn = db
            self._owns_connection = False
        else:
            self.conn = get_connection(db)
            self._owns_connection = True

        init_db(self.conn)

    def close(self) -> None:
        """Close database connection if owned by this repository."""
        if self._owns_connection and self.conn:
            self.conn.close()

    def __enter__(self) -> ArtemisRepository:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # Professors CRUD
    # -------------------------------------------------------------------------

    def create_professor(self, prof: Professor) -> Professor:
        """Insert a new professor record."""
        query = """
        INSERT INTO professors (
            id, name, title, department, institution, email,
            email_status, profile_url, lab_url, scholar_url,
            research_interests_json, sources_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                query,
                (
                    prof.id,
                    prof.name,
                    prof.title,
                    prof.department,
                    prof.institution,
                    prof.email,
                    prof.email_status.value,
                    prof.profile_url,
                    prof.lab_url,
                    prof.scholar_url,
                    json.dumps(prof.research_interests),
                    json.dumps([s.model_dump(mode="json") for s in prof.sources]),
                    prof.created_at.isoformat(),
                    prof.updated_at.isoformat(),
                ),
            )
        return prof

    def get_professor(self, prof_id: str) -> Optional[Professor]:
        """Retrieve a professor by their unique ID."""
        cursor = self.conn.execute(
            "SELECT * FROM professors WHERE id = ?", (prof_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_professor(row)

    def update_professor(self, prof: Professor) -> Professor:
        """Update an existing professor record."""
        prof.updated_at = utc_now()
        query = """
        UPDATE professors SET
            name = ?,
            title = ?,
            department = ?,
            institution = ?,
            email = ?,
            email_status = ?,
            profile_url = ?,
            lab_url = ?,
            scholar_url = ?,
            research_interests_json = ?,
            sources_json = ?,
            updated_at = ?
        WHERE id = ?
        """
        with self.conn:
            cursor = self.conn.execute(
                query,
                (
                    prof.name,
                    prof.title,
                    prof.department,
                    prof.institution,
                    prof.email,
                    prof.email_status.value,
                    prof.profile_url,
                    prof.lab_url,
                    prof.scholar_url,
                    json.dumps(prof.research_interests),
                    json.dumps([s.model_dump(mode="json") for s in prof.sources]),
                    prof.updated_at.isoformat(),
                    prof.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Professor with ID '{prof.id}' not found.")
        return prof

    def list_professors(
        self,
        institution: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Professor]:
        """List professors with optional institution filtering."""
        if institution:
            cursor = self.conn.execute(
                "SELECT * FROM professors WHERE institution = ? ORDER BY name ASC LIMIT ? OFFSET ?",
                (institution, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM professors ORDER BY name ASC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [self._row_to_professor(r) for r in cursor.fetchall()]

    def delete_professor(self, prof_id: str) -> bool:
        """Delete a professor by ID."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM professors WHERE id = ?", (prof_id,)
            )
            return cursor.rowcount > 0

    def _row_to_professor(self, row: sqlite3.Row) -> Professor:
        return Professor(
            id=row["id"],
            name=row["name"],
            title=row["title"],
            department=row["department"],
            institution=row["institution"],
            email=row["email"],
            email_status=VerificationStatus(row["email_status"]),
            profile_url=row["profile_url"],
            lab_url=row["lab_url"],
            scholar_url=row["scholar_url"],
            research_interests=json.loads(row["research_interests_json"]),
            sources=[
                SourceProvenance.model_validate(s)
                for s in json.loads(row["sources_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -------------------------------------------------------------------------
    # Papers CRUD & Junction
    # -------------------------------------------------------------------------

    def create_paper(self, paper: Paper) -> Paper:
        """Insert a research publication record."""
        query = """
        INSERT INTO papers (
            id, title, abstract, published_date, year, venue,
            doi, arxiv_id, openalex_id, url, pdf_url, citation_count,
            author_names_json, sources_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                query,
                (
                    paper.id,
                    paper.title,
                    paper.abstract,
                    paper.published_date,
                    paper.year,
                    paper.venue,
                    paper.doi,
                    paper.arxiv_id,
                    paper.openalex_id,
                    paper.url,
                    paper.pdf_url,
                    paper.citation_count,
                    json.dumps(paper.author_names),
                    json.dumps([s.model_dump(mode="json") for s in paper.sources]),
                    paper.created_at.isoformat(),
                    paper.updated_at.isoformat(),
                ),
            )
        return paper

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """Retrieve a paper by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_paper(row)

    def update_paper(self, paper: Paper) -> Paper:
        """Update an existing paper record."""
        paper.updated_at = utc_now()
        query = """
        UPDATE papers SET
            title = ?,
            abstract = ?,
            published_date = ?,
            year = ?,
            venue = ?,
            doi = ?,
            arxiv_id = ?,
            openalex_id = ?,
            url = ?,
            pdf_url = ?,
            citation_count = ?,
            author_names_json = ?,
            sources_json = ?,
            updated_at = ?
        WHERE id = ?
        """
        with self.conn:
            cursor = self.conn.execute(
                query,
                (
                    paper.title,
                    paper.abstract,
                    paper.published_date,
                    paper.year,
                    paper.venue,
                    paper.doi,
                    paper.arxiv_id,
                    paper.openalex_id,
                    paper.url,
                    paper.pdf_url,
                    paper.citation_count,
                    json.dumps(paper.author_names),
                    json.dumps([s.model_dump(mode="json") for s in paper.sources]),
                    paper.updated_at.isoformat(),
                    paper.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Paper with ID '{paper.id}' not found.")
        return paper

    def list_papers(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        """List all papers ordered by created date."""
        cursor = self.conn.execute(
            "SELECT * FROM papers ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_paper(r) for r in cursor.fetchall()]

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper by ID."""
        with self.conn:
            cursor = self.conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
            return cursor.rowcount > 0

    def link_professor_paper(
        self,
        professor_id: str,
        paper_id: str,
        relationship_type: str = "author",
    ) -> None:
        """Link a professor to a research paper."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO professor_papers (
                    professor_id, paper_id, relationship_type, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (professor_id, paper_id, relationship_type, utc_now().isoformat()),
            )

    def unlink_professor_paper(self, professor_id: str, paper_id: str) -> bool:
        """Remove a link between a professor and a paper."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM professor_papers WHERE professor_id = ? AND paper_id = ?",
                (professor_id, paper_id),
            )
            return cursor.rowcount > 0

    def get_papers_by_professor(self, professor_id: str) -> list[Paper]:
        """Retrieve all papers associated with a given professor."""
        query = """
        SELECT p.* FROM papers p
        JOIN professor_papers pp ON p.id = pp.paper_id
        WHERE pp.professor_id = ?
        ORDER BY p.year DESC NULLS LAST, p.created_at DESC
        """
        cursor = self.conn.execute(query, (professor_id,))
        return [self._row_to_paper(r) for r in cursor.fetchall()]

    def _row_to_paper(self, row: sqlite3.Row) -> Paper:
        return Paper(
            id=row["id"],
            title=row["title"],
            abstract=row["abstract"],
            published_date=row["published_date"],
            year=row["year"],
            venue=row["venue"],
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            openalex_id=row["openalex_id"],
            url=row["url"],
            pdf_url=row["pdf_url"],
            citation_count=row["citation_count"],
            author_names=json.loads(row["author_names_json"]),
            sources=[
                SourceProvenance.model_validate(s)
                for s in json.loads(row["sources_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -------------------------------------------------------------------------
    # Resume Evidence CRUD
    # -------------------------------------------------------------------------

    def create_evidence(self, evidence: ResumeEvidence) -> ResumeEvidence:
        """Insert verified résumé evidence."""
        query = """
        INSERT INTO resume_evidence (
            id, category, title, description, skills_json,
            key_achievements_json, source_reference, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                query,
                (
                    evidence.id,
                    evidence.category.value,
                    evidence.title,
                    evidence.description,
                    json.dumps(evidence.skills),
                    json.dumps(evidence.key_achievements),
                    evidence.source_reference,
                    evidence.created_at.isoformat(),
                    evidence.updated_at.isoformat(),
                ),
            )
        return evidence

    def get_evidence(self, evidence_id: str) -> Optional[ResumeEvidence]:
        """Retrieve résumé evidence by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM resume_evidence WHERE id = ?", (evidence_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_evidence(row)

    def update_evidence(self, evidence: ResumeEvidence) -> ResumeEvidence:
        """Update existing résumé evidence."""
        evidence.updated_at = utc_now()
        query = """
        UPDATE resume_evidence SET
            category = ?,
            title = ?,
            description = ?,
            skills_json = ?,
            key_achievements_json = ?,
            source_reference = ?,
            updated_at = ?
        WHERE id = ?
        """
        with self.conn:
            cursor = self.conn.execute(
                query,
                (
                    evidence.category.value,
                    evidence.title,
                    evidence.description,
                    json.dumps(evidence.skills),
                    json.dumps(evidence.key_achievements),
                    evidence.source_reference,
                    evidence.updated_at.isoformat(),
                    evidence.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Resume evidence with ID '{evidence.id}' not found.")
        return evidence

    def list_evidence(
        self, category: Optional[EvidenceCategory] = None
    ) -> list[ResumeEvidence]:
        """List résumé evidence with optional category filter."""
        if category:
            cursor = self.conn.execute(
                "SELECT * FROM resume_evidence WHERE category = ? ORDER BY created_at DESC",
                (category.value,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM resume_evidence ORDER BY created_at DESC"
            )
        return [self._row_to_evidence(r) for r in cursor.fetchall()]

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete résumé evidence by ID."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM resume_evidence WHERE id = ?", (evidence_id,)
            )
            return cursor.rowcount > 0

    def _row_to_evidence(self, row: sqlite3.Row) -> ResumeEvidence:
        return ResumeEvidence(
            id=row["id"],
            category=EvidenceCategory(row["category"]),
            title=row["title"],
            description=row["description"],
            skills=json.loads(row["skills_json"]),
            key_achievements=json.loads(row["key_achievements_json"]),
            source_reference=row["source_reference"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -------------------------------------------------------------------------
    # Research Briefs CRUD
    # -------------------------------------------------------------------------

    def create_brief(self, brief: ResearchBrief) -> ResearchBrief:
        """Insert a research alignment brief."""
        query = """
        INSERT INTO research_briefs (
            id, professor_id, paper_id, headline, summary,
            core_contributions_json, methodology, potential_alignment,
            matched_evidence_ids_json, open_questions_json,
            confidence_score, confidence_notes, sources_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                query,
                (
                    brief.id,
                    brief.professor_id,
                    brief.paper_id,
                    brief.headline,
                    brief.summary,
                    json.dumps(brief.core_contributions),
                    brief.methodology,
                    brief.potential_alignment,
                    json.dumps(brief.matched_evidence_ids),
                    json.dumps(brief.open_questions),
                    brief.confidence_score,
                    brief.confidence_notes,
                    json.dumps([s.model_dump(mode="json") for s in brief.sources]),
                    brief.created_at.isoformat(),
                    brief.updated_at.isoformat(),
                ),
            )
        return brief

    def get_brief(self, brief_id: str) -> Optional[ResearchBrief]:
        """Retrieve a research brief by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM research_briefs WHERE id = ?", (brief_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_brief(row)

    def update_brief(self, brief: ResearchBrief) -> ResearchBrief:
        """Update an existing research brief."""
        brief.updated_at = utc_now()
        query = """
        UPDATE research_briefs SET
            paper_id = ?,
            headline = ?,
            summary = ?,
            core_contributions_json = ?,
            methodology = ?,
            potential_alignment = ?,
            matched_evidence_ids_json = ?,
            open_questions_json = ?,
            confidence_score = ?,
            confidence_notes = ?,
            sources_json = ?,
            updated_at = ?
        WHERE id = ?
        """
        with self.conn:
            cursor = self.conn.execute(
                query,
                (
                    brief.paper_id,
                    brief.headline,
                    brief.summary,
                    json.dumps(brief.core_contributions),
                    brief.methodology,
                    brief.potential_alignment,
                    json.dumps(brief.matched_evidence_ids),
                    json.dumps(brief.open_questions),
                    brief.confidence_score,
                    brief.confidence_notes,
                    json.dumps([s.model_dump(mode="json") for s in brief.sources]),
                    brief.updated_at.isoformat(),
                    brief.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Research brief with ID '{brief.id}' not found.")
        return brief

    def list_briefs_by_professor(self, professor_id: str) -> list[ResearchBrief]:
        """List all research briefs generated for a professor."""
        cursor = self.conn.execute(
            "SELECT * FROM research_briefs WHERE professor_id = ? ORDER BY created_at DESC",
            (professor_id,),
        )
        return [self._row_to_brief(r) for r in cursor.fetchall()]

    def delete_brief(self, brief_id: str) -> bool:
        """Delete a research brief by ID."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM research_briefs WHERE id = ?", (brief_id,)
            )
            return cursor.rowcount > 0

    def _row_to_brief(self, row: sqlite3.Row) -> ResearchBrief:
        return ResearchBrief(
            id=row["id"],
            professor_id=row["professor_id"],
            paper_id=row["paper_id"],
            headline=row["headline"],
            summary=row["summary"],
            core_contributions=json.loads(row["core_contributions_json"]),
            methodology=row["methodology"],
            potential_alignment=row["potential_alignment"],
            matched_evidence_ids=json.loads(row["matched_evidence_ids_json"]),
            open_questions=json.loads(row["open_questions_json"]),
            confidence_score=row["confidence_score"],
            confidence_notes=row["confidence_notes"],
            sources=[
                SourceProvenance.model_validate(s)
                for s in json.loads(row["sources_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -------------------------------------------------------------------------
    # Email Drafts CRUD
    # -------------------------------------------------------------------------

    def create_draft(self, draft: EmailDraft) -> EmailDraft:
        """Insert an email draft."""
        query = """
        INSERT INTO email_drafts (
            id, professor_id, brief_id, recipient_email, recipient_name,
            subject, body, rationale, status, gmail_draft_id,
            verification_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                query,
                (
                    draft.id,
                    draft.professor_id,
                    draft.brief_id,
                    draft.recipient_email,
                    draft.recipient_name,
                    draft.subject,
                    draft.body,
                    draft.rationale,
                    draft.status.value,
                    draft.gmail_draft_id,
                    draft.verification_notes,
                    draft.created_at.isoformat(),
                    draft.updated_at.isoformat(),
                ),
            )
        return draft

    def get_draft(self, draft_id: str) -> Optional[EmailDraft]:
        """Retrieve an email draft by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM email_drafts WHERE id = ?", (draft_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_draft(row)

    def update_draft(self, draft: EmailDraft) -> EmailDraft:
        """Update an existing email draft."""
        draft.updated_at = utc_now()
        query = """
        UPDATE email_drafts SET
            brief_id = ?,
            recipient_email = ?,
            recipient_name = ?,
            subject = ?,
            body = ?,
            rationale = ?,
            status = ?,
            gmail_draft_id = ?,
            verification_notes = ?,
            updated_at = ?
        WHERE id = ?
        """
        with self.conn:
            cursor = self.conn.execute(
                query,
                (
                    draft.brief_id,
                    draft.recipient_email,
                    draft.recipient_name,
                    draft.subject,
                    draft.body,
                    draft.rationale,
                    draft.status.value,
                    draft.gmail_draft_id,
                    draft.verification_notes,
                    draft.updated_at.isoformat(),
                    draft.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Email draft with ID '{draft.id}' not found.")
        return draft

    def list_drafts(
        self,
        status: Optional[EmailDraftStatus] = None,
        professor_id: Optional[str] = None,
    ) -> list[EmailDraft]:
        """List email drafts with optional status or professor filter."""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if professor_id:
            conditions.append("professor_id = ?")
            params.append(professor_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM email_drafts {where_clause} ORDER BY created_at DESC"

        cursor = self.conn.execute(query, tuple(params))
        return [self._row_to_draft(r) for r in cursor.fetchall()]

    def delete_draft(self, draft_id: str) -> bool:
        """Delete an email draft by ID."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM email_drafts WHERE id = ?", (draft_id,)
            )
            return cursor.rowcount > 0

    def _row_to_draft(self, row: sqlite3.Row) -> EmailDraft:
        return EmailDraft(
            id=row["id"],
            professor_id=row["professor_id"],
            brief_id=row["brief_id"],
            recipient_email=row["recipient_email"],
            recipient_name=row["recipient_name"],
            subject=row["subject"],
            body=row["body"],
            rationale=row["rationale"],
            status=EmailDraftStatus(row["status"]),
            gmail_draft_id=row["gmail_draft_id"],
            verification_notes=row["verification_notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
