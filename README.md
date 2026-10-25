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

## Research Intelligence Web Dashboard (Streamlit)

A.R.T.E.M.I.S. includes a local web application built with Streamlit.

### Launching the Dashboard

Ensure your virtual environment is active, then run:

```bash
streamlit run app.py
```

The application will launch and bind strictly to `http://localhost:8501`.

### Key Dashboard Views

1. **📊 Overview Dashboard (Section A)**: Real-time SQLite counts (discovered faculty, tracked papers, generated briefs, pending drafts), recent scouting history, recent faculty and publications, and graceful empty states.
2. **🛰️ Research Scout (Section B)**: Enter an institute faculty directory URL (e.g. `https://homecse.iitd.ac.in/faculty/`), research keywords, and crawler limits. Executes polite crawling and queries academic papers with clear progress feedback.
3. **🎓 Professor Explorer (Section C)**: Search and filter discovered faculty by name, department, institution, or email verification status (`Verified Official`, `Unverified Scraped`, `No Email Listed`). Direct access to official profile, lab website, and Google Scholar URLs.
4. **📑 Paper Explorer (Section D)**: Search and filter publications with clear distinction between bibliographic metadata and verified faculty author links. Explicit `[Abstract-Only Available]` boundary notices and persistent DOI / arXiv links.
5. **🧠 Research Brief Workspace (Section E)**: Select a professor and paper, then synthesize evidence-grounded research briefs. Features prominent `[Abstract-Based Brief]` labels, paper methodology analysis, bounded limitations, matching student résumé evidence, skill gap disclosures, and professor discussion questions.
6. **✉️ Outreach Draft Review (Section F)**: Review, edit, and audit personalized cold outreach emails. Includes a **Live Automated Quality Control Card** verifying word count ($\le 300$ words), anti-hallucination checks (flagging forbidden phrases like *"as we discussed"* or *"saw your job posting"*), and email deliverability warnings. Edits save directly to SQLite.
7. **⚙️ Settings & System Status (Section G)**: SQLite database path manager, active LLM provider status (Mock vs. Gemini API with masked keys), crawler User-Agent and politeness configurations, and operational diagnostics.

---

## Project Structure

```text
ARTEMIS/
├── .env.example              # Environment configuration template
├── .gitignore                # Exclusion rules for local DBs, venvs, and secrets
├── .streamlit/               # Streamlit configuration (dark theme, localhost binding)
│   └── config.toml
├── app.py                    # Streamlit dashboard entrypoint
├── pyproject.toml            # PEP 517/621 package metadata, dependencies (streamlit, pypdf)
├── README.md                 # Project documentation and quickstart guide
├── HANDOFF.md                # Verification findings, edge cases, and handoff report
├── src/
│   └── artemis/
│       ├── __init__.py
│       ├── cli.py            # CLI commands (scout, ingest-resume, brief, draft, match)
│       ├── service.py        # ArtemisScoutingService orchestration
│       ├── models/           # Pydantic v2 domain schemas with validation & provenance
│       │   ├── __init__.py
│       │   ├── common.py     # VerificationStatus enum and SourceProvenance model
│       │   ├── professor.py  # Professor entity with email validation and URLs
│       │   ├── paper.py      # Research Paper entity (DOI, arXiv, OpenAlex)
│       │   ├── resume.py     # ResumeEvidence entity with raw_snippet & UNVERIFIED state
│       │   ├── brief.py      # ResearchBrief with limitations, gaps, and open questions
│       │   ├── email.py      # EmailDraft entity with draft_pending status & audit trail
│       │   └── run.py        # ScoutingRun entity tracking crawler history
│       ├── db/               # SQLite persistence layer
│       │   ├── __init__.py
│       │   ├── connection.py # Connection factory (foreign keys, WAL mode, Row factory)
│       │   ├── schema.py     # Relational tables, indexes, and schema migrations
│       │   └── repository.py # ArtemisRepository providing full CRUD and relations
│       ├── crawler/          # Polite web crawler and university directory parser
│       │   ├── __init__.py
│       │   ├── client.py     # PoliteHttpClient with per-domain rate limiting
│       │   └── faculty_parser.py # Static HTML & specialized university DOM parsers
│       ├── scouting/         # Bibliographic academic discovery & paper ranking
│       │   ├── __init__.py
│       │   ├── clients.py    # OpenAlex, arXiv, and Crossref API clients
│       │   └── ranker.py     # Paper ranker and author affiliation disambiguation
│       ├── resume/           # Student résumé ingestion engine
│       │   ├── __init__.py
│       │   └── extractor.py  # PDF, TXT, MD parser extracting structured ResumeEvidence
│       ├── llm/              # Replaceable LLM interface
│       │   ├── __init__.py
│       │   └── provider.py   # LLMProvider, MockLLMProvider, and GeminiLLMProvider
│       ├── brief/            # Research brief synthesis
│       │   ├── __init__.py
│       │   └── synthesizer.py# Grounded synthesis with abstract labeling & guardrails
│       ├── email/            # Outreach email drafting
│       │   ├── __init__.py
│       │   └── generator.py  # Review-only cold draft generator with safety audits
│       ├── ui/               # Research Intelligence Dashboard
│       │   ├── __init__.py
│       │   ├── theme.py      # Dark navy/charcoal & gold custom CSS
│       │   ├── state.py      # Session state and repository context manager
│       │   ├── components/
│       │   │   └── quality.py# Cold email quality control & anti-hallucination checks
│       │   └── views/
│       │       ├── dashboard.py  # Section A: Overview Dashboard
│       │       ├── scout.py      # Section B: Research Scout
│       │       ├── professors.py # Section C: Professor Explorer
│       │       ├── papers.py     # Section D: Paper Explorer
│       │       ├── briefs.py     # Section E: Research Brief Workspace
│       │       ├── drafts.py     # Section F: Outreach Draft Review
│       │       └── settings.py   # Section G: Settings & System Status
│       └── utils/
│           ├── __init__.py
│           └── ids.py        # Prefixed human-readable unique ID generator
├── tests/                    # Complete pytest suite (118 unit & integration tests)
│   ├── conftest.py           # Shared fixtures (in-memory DB, sample models, fixtures)
│   ├── test_models.py        # Domain model validation & constraint tests
│   ├── test_repository.py    # SQLite repository CRUD, junction, and cascade tests
│   ├── test_crawler.py       # Polite crawling & directory layout tests
│   ├── test_scouting.py      # OpenAlex, arXiv, Crossref & ranking tests
│   ├── test_service.py       # End-to-end faculty scouting pipeline test
│   ├── test_resume.py        # PDF, Markdown, and TXT résumé parsing tests
│   ├── test_llm.py           # Mock and Gemini LLM provider tests
│   ├── test_brief_synthesizer.py # Grounding, abstract labeling & hallucination rejection
│   ├── test_email_generator.py # Cold email draft generation and safety tests
│   ├── test_cli.py           # CLI argument parsing and error handling tests
│   ├── test_milestone3_service_and_cli.py # M3 pipeline & CLI integration tests
│   ├── test_ui.py            # Quality control, word count, anti-hallucination & UI tests
│   └── test_smoke_real_web.py # Optional real-world university live smoke test
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

## CLI Usage: Complete Workflow

A.R.T.E.M.I.S. provides modular subcommands for each stage of academic discovery, résumé analysis, research synthesis, and outreach draft generation.

### 1. Ingest Student Résumé (`ingest-resume`)

Extracts factual claims (skills, projects, coursework, research) from `.pdf`, `.md`, or `.txt` résumés into structured `ResumeEvidence` models. Every claim preserves its source snippet and starts as `UNVERIFIED` until reviewed by the student.

```bash
artemis ingest-resume <RESUME_FILE> [--db DB_PATH]
```

**Example:**
```bash
artemis ingest-resume ./student_cv.pdf --db artemis.db
```

### 2. Scout University Faculty & Papers (`scout`)

Scouts a university faculty directory, parses public faculty details, and retrieves publications from OpenAlex and arXiv matching research keywords.

```bash
artemis scout <DIRECTORY_URL> -k <KEYWORDS...> [-f MAX_FACULTY] [-p MAX_PAPERS] [-i INSTITUTION] [--db DB_PATH]
```

**Example:**
```bash
artemis scout https://homecse.iitd.ac.in/faculty/ -k "systems" "networks" -f 3 -p 2 --db artemis.db
```

### 3. Synthesize Grounded Research Brief (`brief`)

Connects a discovered publication with authentic student résumé evidence in the database.
- Strictly labels briefs as `[Abstract-Based Brief]` when full text is missing, preventing hallucinated methodologies.
- Rejects fabricated evidence IDs not present in student evidence.
- Reflects uncertainty (confidence <= 0.35) and documents specific background gaps when evidence is missing or unrelated.

```bash
artemis brief --prof <PROFESSOR_ID> --paper <PAPER_ID> [--db DB_PATH]
```

**Example:**
```bash
artemis brief --prof prof_16f28cefe74c --paper paper_8a54adc1f4cd --db artemis.db
```

### 4. Generate Cold Outreach Email Draft (`draft`)

Generates a review-only outreach draft connecting the student's authentic qualifications to one specific paper.
- Sets status strictly to `draft_pending` for user review (emails are **never** sent automatically).
- Strictly forbids hallucinated prior relationships (e.g. "as we discussed") or phantom vacancies (e.g. "saw your posting").
- Flags unverified professor email addresses with explicit safety warnings.

```bash
artemis draft --prof <PROFESSOR_ID> --brief <BRIEF_ID> [--name STUDENT_NAME] [--db DB_PATH]
```

**Example:**
```bash
artemis draft --prof prof_16f28cefe74c --brief brief_698b3b3c26c4 --name "Alex Kumar" --db artemis.db
```

### 5. Unified End-to-End Pipeline (`match`)

Runs the entire workflow in one command: scouts faculty and papers, ingests the student's résumé, synthesizes grounded briefs, and generates review-ready email drafts.

```bash
artemis match <DIRECTORY_URL> -r <RESUME_FILE> -k <KEYWORDS...> [-f MAX_FACULTY] [--name STUDENT_NAME] [--db DB_PATH]
```

**Example:**
```bash
artemis match https://www.cse.iitm.ac.in/outerfaculty.php -r ./my_cv.md -k "cryptography" "security" -f 2 --name "Piyush Sahoo"
```

---

## LLM Configuration: Replaceable Provider Interface

A.R.T.E.M.I.S. decouples brief synthesis and email drafting from any specific LLM vendor via `LLMProvider`.

- **Mock Provider (`mock`)**: Default for testing and offline development. Generates deterministic, grounded JSON schemas with zero external network calls or costs.
- **Gemini Provider (`gemini`)**: Production provider connecting to Google Gemini (e.g. `gemini-2.0-flash`) via `httpx`. Never hardcodes keys.

Configure in `.env`:
```env
ARTEMIS_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

If `ARTEMIS_LLM_PROVIDER` is set to `mock` or `GEMINI_API_KEY` is omitted, ARTEMIS defaults gracefully to the offline deterministic provider.

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

## Crawler Identity & Polite Crawling

ARTEMIS identifies itself to university web servers and public bibliographic APIs using a polite, honest User-Agent header:

```text
ARTEMIS-AcademicScout/0.2.0 (+https://github.com/piyushSahooDB/ARTEMIS; mailto:<email>; polite student research assistant)
```

You can customize this in your `.env` file:
```env
ARTEMIS_CONTACT_EMAIL=student@university.edu
# Or set a full custom User-Agent:
# ARTEMIS_USER_AGENT=MyCustomResearchAgent/1.0 (+https://my-site.org; mailto:me@my-site.org)
```

---

## Ground Truth & Verification Semantics

To uphold strict anti-hallucination and truthfulness standards:
- **Email Status**:
  - `[listed on official page; deliverability unverified]`: Indicates the email was explicitly published on the institution's official faculty directory or individual profile page. It does **not** prove SMTP deliverability or that the mailbox is currently active (ARTEMIS never sends test emails or pings mail servers).
  - Missing emails are left as `None` / `[Not publicly listed on directory / unverified]` and never guessed.
- **Author Publication Matches**:
  - `[AFFILIATION MATCHED IN METADATA]` (`confidence: 1.00`): The author's institutional affiliation string in OpenAlex, arXiv, or Crossref metadata explicitly matches the target university or institute. This provides strong bibliographic evidence of authorship, but is not biometric identity proof.
  - `[UNCERTAIN (Name-Only Match)]` (`confidence: 0.40`): The paper author name matches the professor, but the publication metadata either lacks an affiliation or lists a different institution. The paper is retained if topically relevant, but clearly flagged as unconfirmed.
- **Idempotent Persistence**:
  - Re-running scouting against an existing SQLite database updates existing faculty and publications by business keys (`(name, institution)`, `email`, `DOI`, `arXiv ID`, `title`) without creating duplicates.

---

## Known Limitations & Design Boundaries

1. **Client-Side SPAs**:
   - ARTEMIS parses server-rendered HTML pages. If a university directory is built purely as a client-side JavaScript Single Page Application (e.g. IIT Bombay CSE's Angular `<app-root>`), ARTEMIS raises a clean, explicit `JavaScriptRenderedPageError` explaining that browser JavaScript execution is required, rather than silently fabricating or returning empty results.
2. **Polite Rate Limiting**:
   - Requests enforce a per-domain interval (default 0.5s) and handle HTTP 429 `Retry-After`. Deep crawling is bounded by `--max-faculty` to prevent unintended burden on academic infrastructure.
3. **Identity Disambiguation**:
   - Author names matching common names are cross-referenced with institutional affiliations from OpenAlex, arXiv, and Crossref. If affiliation metadata does not match, the paper is explicitly tagged `UNCERTAIN (Name-Only Match)` with lower confidence (`0.40`), maintaining strict anti-hallucination standards.
4. **Obfuscated Email Formats**:
   - ARTEMIS automatically deobfuscates standard institutional patterns like `name[at]cse[dot]iitm[dot]ac[dot]in` and mailto links. If an email is published as an image or CAPTCHA, it remains `None`.

---

## Milestone Roadmap

- [x] **Milestone 1: Project Foundation**
  - Package structure, dependency configuration, `.gitignore`, `.env.example`.
  - Pydantic models with strict validation, source provenance, and verification states.
  - SQLite repository layer with full CRUD, junction tables, and cascade safety.
  - Comprehensive unit and integration test suite (45 tests passing).
  - Executable quickstart demonstration.
- [x] **Milestone 2: Faculty Discovery & Academic Paper Scouting**
  - Polite HTTP client with rate limiting, timeouts, and configurable academic User-Agent.
  - Static HTML faculty directory parser extracting names, titles, emails, interests, and profile links.
  - Specialized layouts for Indian institutes: Elementor (IIT Delhi), HTML5 data-attribute cards (IIT Madras), Bootstrap grids (IIT Kanpur).
  - Bounded profile subpage exploration for Google Scholar and lab website links.
  - Client-side SPA detection (e.g. IIT Bombay Angular `<app-root>`) and graceful reporting.
  - OpenAlex, arXiv, and Crossref clients fetching publications without web scraping.
  - Author identity verification against institutional affiliation metadata.
  - Paper deduplication by canonical DOI, arXiv ID, and normalized title.
  - Paper ranker separating topic relevance from author identity confidence.
  - CLI command `artemis scout` with formatted table and idempotent SQLite persistence.
  - 74 unit tests with mocked payloads + manual live smoke test.
- [x] **Milestone 3: Student Résumé Parsing & Research Brief Matching**
  - Text & PDF résumé ingestion with `pypdf`, preserving exact snippets and unverified claim status.
  - Structured `ResumeEvidence` models categorizing technical skills, coursework, and projects.
  - Replaceable `LLMProvider` interface with deterministic offline `MockLLMProvider` and production `GeminiLLMProvider`.
  - Research brief synthesizer enforcing `[Abstract-Based Brief]` labeling when full text is missing.
  - Anti-hallucination guardrails: rejecting fabricated evidence IDs, reflecting uncertainty for unrelated backgrounds.
  - Review-first cold email draft generator (`draft_pending`) referencing one specific paper and authentic evidence.
  - CLI subcommands: `ingest-resume`, `brief`, `draft`, and unified `match` pipeline.
  - 106 passing offline unit & integration tests with zero network dependencies.
- [ ] **Milestone 4: Personalized Outreach & Gmail Draft Sync**
  - Google OAuth 2.0 Gmail draft creator (drafts only, never sending).
  - Draft synchronization status (`gmail_synced`) and local ID mapping.
