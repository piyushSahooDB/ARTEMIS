"""Database schema definition and table initialization for ARTEMIS."""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
-- Professors table
CREATE TABLE IF NOT EXISTS professors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    department TEXT,
    institution TEXT NOT NULL,
    email TEXT,
    email_status TEXT NOT NULL,
    profile_url TEXT,
    lab_url TEXT,
    scholar_url TEXT,
    research_interests_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Research papers table
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    published_date TEXT,
    year INTEGER,
    venue TEXT,
    doi TEXT,
    arxiv_id TEXT,
    openalex_id TEXT,
    url TEXT,
    pdf_url TEXT,
    citation_count INTEGER,
    author_names_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Professor-to-paper junction table
CREATE TABLE IF NOT EXISTS professor_papers (
    professor_id TEXT NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'author',
    created_at TEXT NOT NULL,
    PRIMARY KEY (professor_id, paper_id)
);

-- Verified resume evidence table
CREATE TABLE IF NOT EXISTS resume_evidence (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    skills_json TEXT NOT NULL DEFAULT '[]',
    key_achievements_json TEXT NOT NULL DEFAULT '[]',
    source_reference TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    raw_snippet TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Research briefs table
CREATE TABLE IF NOT EXISTS research_briefs (
    id TEXT PRIMARY KEY,
    professor_id TEXT NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    paper_id TEXT REFERENCES papers(id) ON DELETE SET NULL,
    headline TEXT NOT NULL,
    summary TEXT NOT NULL,
    core_contributions_json TEXT NOT NULL DEFAULT '[]',
    methodology TEXT,
    potential_alignment TEXT NOT NULL,
    matched_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    open_questions_json TEXT NOT NULL DEFAULT '[]',
    confidence_score REAL NOT NULL DEFAULT 1.0,
    confidence_notes TEXT,
    sources_json TEXT NOT NULL DEFAULT '[]',
    limitations_json TEXT NOT NULL DEFAULT '[]',
    gaps_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Email drafts table
CREATE TABLE IF NOT EXISTS email_drafts (
    id TEXT PRIMARY KEY,
    professor_id TEXT NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    brief_id TEXT REFERENCES research_briefs(id) ON DELETE SET NULL,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL,
    gmail_draft_id TEXT,
    verification_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indexes for performance and quick searches
CREATE INDEX IF NOT EXISTS idx_professors_institution ON professors(institution);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_professor ON research_briefs(professor_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_professor ON email_drafts(professor_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_status ON email_drafts(status);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize all database tables and indexes, applying backward-compatible migrations."""
    with conn:
        conn.executescript(SCHEMA_SQL)
        cursor = conn.execute("PRAGMA table_info(resume_evidence)")
        cols = {row[1] for row in cursor.fetchall()}
        if "verification_status" not in cols:
            conn.execute("ALTER TABLE resume_evidence ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'unverified'")
        if "raw_snippet" not in cols:
            conn.execute("ALTER TABLE resume_evidence ADD COLUMN raw_snippet TEXT")

        brief_cursor = conn.execute("PRAGMA table_info(research_briefs)")
        brief_cols = {row[1] for row in brief_cursor.fetchall()}
        if "limitations_json" not in brief_cols:
            conn.execute("ALTER TABLE research_briefs ADD COLUMN limitations_json TEXT NOT NULL DEFAULT '[]'")
        if "gaps_json" not in brief_cols:
            conn.execute("ALTER TABLE research_briefs ADD COLUMN gaps_json TEXT NOT NULL DEFAULT '[]'")
