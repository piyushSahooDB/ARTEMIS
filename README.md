# A.R.T.E.M.I.S.
**Autonomous Research Tracking, Exploration, Matching & Intelligent Scouting**

A local-first Python agent that empowers university students to scout prospective research advisors, comprehend their recent publications, align authentic qualifications from their résumé, and prepare personalized outreach drafts.

---

## Core Principles & Safety Guardrails

- **Local-First & Light**: Persistent storage via SQLite with WAL mode and foreign key integrity. No unnecessary external vector databases, microservices, or complex multi-agent frameworks.
- **Strict Anti-Hallucination**: Never fabricate professor details, contact emails, research claims, or student qualifications. Missing information is left as `None` or explicitly marked `UNVERIFIED`.
- **Factual Provenance**: Every entity and assertion records source URLs, extraction timestamps, and grounding evidence snippets.
- **Review-Only Outreach**: The system only prepares drafts. Emails are never sent automatically.

---

## Project Structure

```text
ARTEMIS/
├── .env.example              # Environment configuration template
├── .gitignore                # Exclusion rules for local DBs, venvs, and secrets
├── pyproject.toml            # PEP 517/621 package metadata and pytest config
├── README.md                 # Project documentation and quickstart guide
├── src/
│   └── artemis/
│       ├── __init__.py
│       ├── models/           # Pydantic v2 domain schemas with validation & provenance
│       │   ├── __init__.py
│       │   ├── common.py     # VerificationStatus enum and SourceProvenance model
│       │   ├── professor.py  # Professor entity with email validation and URLs
│       │   ├── paper.py      # Research Paper entity (DOI, arXiv, OpenAlex)
│       │   ├── resume.py     # ResumeEvidence entity categorizing student achievements
│       │   ├── brief.py      # ResearchBrief linking paper findings to student skills
│       │   └── email.py      # EmailDraft entity with status lifecycle and audit trail
│       ├── db/               # SQLite persistence layer
│       │   ├── __init__.py
│       │   ├── connection.py # Connection factory (foreign keys, WAL mode, Row factory)
│       │   ├── schema.py     # Relational tables, indexes, and migrations
│       │   └── repository.py # ArtemisRepository providing full CRUD and relations
│       └── utils/
│           ├── __init__.py
│           └── ids.py        # Prefixed human-readable unique ID generator
├── tests/                    # Complete pytest suite
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures (in-memory DB, sample models)
│   ├── test_models.py        # Domain model validation & constraint tests
│   └── test_repository.py    # SQLite repository CRUD, junction, and cascade tests
└── examples/
    └── quickstart.py         # End-to-end runnable foundation demonstration
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (tested with 3.10 and 3.12)
- Git

### 2. Environment Setup

Create and activate a virtual environment:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install the package and development dependencies in editable mode:

```bash
pip install -e .[dev]
```

Copy the example environment configuration:

```bash
cp .env.example .env
```

---

## Running Tests

Run the complete test suite with `pytest`:

```bash
pytest
```

For verbose output with execution timings:

```bash
pytest -v --durations=10
```

---

## Running the Minimal Foundation Example

Execute the standalone quickstart script to verify repository initialization, model serialization, and relation querying:

```bash
python examples/quickstart.py
```

This script demonstrates:
1. Connecting to a local SQLite repository.
2. Registering an academic researcher with official web source provenance.
3. Storing a verified conference paper and linking it to the researcher.
4. Adding verified résumé project evidence.
5. Synthesizing a research brief connecting the student's background to the paper.
6. Generating an outreach email draft marked `draft_pending` for user review.

---

## CLI Usage: Faculty Discovery & Paper Scouting

A.R.T.E.M.I.S. provides a command-line interface to scout university faculty directories and match academic publications against research keywords.

### Command Syntax

```bash
artemis scout <DIRECTORY_URL> -k <KEYWORDS...> [-f MAX_FACULTY] [-p MAX_PAPERS] [--db DB_PATH] [--no-persist]
```

or via python module:

```bash
python -m artemis scout <DIRECTORY_URL> -k <KEYWORDS...>
```

### Options

| Flag | Default | Description |
|---|---|---|
| `<DIRECTORY_URL>` / `-u` | *Required* | Official university faculty directory URL (HTML) |
| `-k`, `--keywords` | `[]` | Space-separated research keywords (e.g. `distributed consensus "fault tolerance"`) |
| `-f`, `--max-faculty` | `5` | Maximum number of faculty members to scout |
| `-p`, `--max-papers` | `3` | Maximum number of papers retrieved per professor |
| `--db` | `artemis.db`| SQLite database file to persist discovered entities |
| `--no-persist` | `False` | Run scouting without writing to SQLite |

### Example CLI Command

```bash
artemis scout https://www.cs.princeton.edu/people/faculty -k "machine learning" "systems" -f 3 -p 2
```

---

## Manual Smoke-Test Procedure

To test live faculty directory scraping and public academic API discovery against a real university website:

```bash
# Run against the default test URL (Princeton CS Faculty Directory):
python tests/test_smoke_real_web.py

# Or supply any real server-rendered university faculty page:
python tests/test_smoke_real_web.py https://www.cs.princeton.edu/people/faculty
```

To run the full test suite including live web tests:
```bash
RUN_LIVE_TESTS=1 pytest
```

---

## Known Limitations & Design Boundaries

1. **Client-Side SPAs**:
   - ARTEMIS parses server-rendered HTML pages. If a university directory is built purely as a client-side JavaScript Single Page Application (e.g. empty `<div id="root"></div>`), ARTEMIS raises a clean, explicit `JavaScriptRenderedPageError` rather than silently fabricating or returning empty results.
2. **Polite Rate Limiting**:
   - Requests enforce a per-domain interval (default 0.5s) and handle HTTP 429 `Retry-After`. Deep crawling is bounded by `--max-faculty` to prevent unintended burden on academic infrastructure.
3. **Identity Disambiguation**:
   - Author names matching common names are cross-referenced with institutional affiliations from OpenAlex, arXiv, and Crossref. If affiliation metadata does not match, the paper is explicitly tagged `UNCERTAIN (Name-Only Match)` with lower confidence (`0.40`), maintaining strict anti-hallucination standards.

---

## Milestone Roadmap

- [x] **Milestone 1: Project Foundation**
  - Package structure, dependency configuration, `.gitignore`, `.env.example`.
  - Pydantic models with strict validation, source provenance, and verification states.
  - SQLite repository layer with full CRUD, junction tables, and cascade safety.
  - Comprehensive unit and integration test suite (45 tests passing).
  - Executable quickstart demonstration.
- [x] **Milestone 2: Faculty Discovery & Academic Paper Scouting**
  - Polite HTTP client with rate limiting, timeouts, and academic User-Agent.
  - Static HTML faculty directory parser extracting names, titles, emails, interests, and profile links.
  - Bounded profile subpage exploration for Google Scholar and lab website links.
  - Client-side SPA detection and graceful reporting.
  - OpenAlex, arXiv, and Crossref clients fetching publications without web scraping.
  - Author identity verification against institutional affiliation.
  - Paper deduplication by canonical DOI, arXiv ID, and normalized title.
  - Paper ranker separating topic relevance from author identity confidence.
  - CLI command `artemis scout` with formatted table and SQLite persistence.
  - 72 unit tests with mocked payloads + manual live smoke test.
- [ ] **Milestone 3: Student Résumé Parsing & Research Brief Matching**
  - Résumé text extraction and structured evidence ingestion.
  - Replaceable LLM interface generating grounded research briefs and alignment rationales.
- [ ] **Milestone 4: Personalized Outreach & Gmail Draft Sync**
  - Review-first draft generator.
  - Google OAuth 2.0 Gmail draft creator (drafts only, never sending).
