# A.R.T.E.M.I.S. — Milestone 2 Verification & Handoff Report

**Date**: October 25, 2026  
**Status**: Milestone 2 Complete & Validated on Real-World Academic Portals  
**Test Suite**: 74 Unit Tests Passed (0 Failed, 1 Skipped — Live Web Smoke Test)  

---

## 1. What Was Actually Verified vs. Merely Assumed

| Dimension | Initial Assumption / Claim | Actual Verified Reality & Resolution |
|---|---|---|
| **Crawler User-Agent** | Assumed standard agent was active. | Initial default was a placeholder string (`github.com/artemis-agent; mailto:artemis-scout@example.edu`). **Fixed**: Replaced with polite, honest identity pointing to repository (`https://github.com/piyushSahooDB/ARTEMIS`) and user-configurable via `ARTEMIS_CONTACT_EMAIL` or `ARTEMIS_USER_AGENT` environment variables. |
| **Email Verification** | Displaying `[verified]` implied deliverability or confirmed active inbox. | Merely scraping an email from HTML proves it was published on that page; it does **not** prove SMTP deliverability or mailbox responsiveness. **Fixed**: Updated model docstrings and CLI labels to `[listed on official page; deliverability unverified]`. ARTEMIS never tests SMTP or pings mail servers. |
| **Paper Author Confidence** | Publication match marked `VERIFIED AFFILIATION` with `1.00` confidence could be mistaken for biometric identity proof. | Author match is bibliometric metadata comparison. An affiliation match indicates high confidence (`1.00`), but name-only matches without affiliation must remain `UNCERTAIN (Name-Only Match)` with confidence `0.40`. **Fixed**: Clarified semantics and terminal labels. |
| **Indian Institute Parsing** | Assumed standard Western `div.faculty-card` or `table` selectors were sufficient. | Indian institutes use varied DOM architectures: IIT Delhi uses WordPress/Elementor (`div.single-team-area`), IIT Madras uses custom HTML5 data-attribute cards (`div.fac-card` with `data-mail="name[at]cse[dot]iitm[dot]ac[dot]in"`), and IIT Bombay is a client-side Angular SPA (`<app-root>`). **Fixed**: Added support for Elementor cards, HTML5 data attributes, email deobfuscation, and Angular SPA detection. |
| **Institution Domain Extraction** | Assumed splitting hostname by dots (`parts[-2].capitalize()`) would derive the university name. | On country-code second-level domains (`.ac.in`, `.ac.uk`), `parts[-2]` is `"ac"`, producing `"Ac University"`! This broke downstream OpenAlex affiliation matching. **Fixed**: Implemented canonical domain mappings (`iitd` → `"Indian Institute of Technology Delhi"`, `iitm` → `"Indian Institute of Technology Madras"`, etc.) and added an optional `-i / --institution` CLI override. |
| **SQLite Idempotency** | Assumed re-running scouting would update existing database records. | Because Pydantic models generate a fresh UUID on every run, `repo.get_professor(prof.id)` never matched existing records, inserting duplicates on every run (run 1: 3 profs; run 2: 6 profs). **Fixed**: Added repository lookups by business keys (`(name, institution)`, `email`, `DOI`, `arXiv ID`, `title`) to ensure true idempotency. |

---

## 2. Bugs & Misleading Claims Found and Fixed

1. **Crawler Identity Discrepancy**:
   - *Issue*: Crawler identified itself with nonexistent `artemis-agent` GitHub account and `artemis-scout@example.edu` contact.
   - *Fix*: Created `get_default_user_agent()` in `src/artemis/crawler/client.py` using repository origin `https://github.com/piyushSahooDB/ARTEMIS` and optional environment variable `ARTEMIS_CONTACT_EMAIL`.
2. **Domain Parsing Bug (`"Ac University"` issue)**:
   - *Issue*: `homecse.iitd.ac.in` domain was parsed as `parts[-2] = "ac"`, producing `"Ac University"`. When OpenAlex returned `"Indian Institute of Technology Delhi"`, ARTEMIS falsely reported affiliation mismatch.
   - *Fix*: Added `KNOWN_INSTITUTION_DOMAINS` dictionary in `src/artemis/crawler/faculty_parser.py` covering major Indian IITs, NITs, IISc, IIITs, BITS, and global universities, plus robust ccTLD domain suffix handling.
3. **Greedy Regex Navigation Capture**:
   - *Issue*: Scanning HTML headers for `[A-Za-z\s]+(?:University|Institute of Technology)` greedily captured skip links like `Skip to content Computer Science and Engineering Indian Institute of Technology`.
   - *Fix*: Prioritized canonical domain lookup over raw header scraping and tightened pattern boundaries with `\b(Indian Institute of Technology\s+[A-Z][a-z]+|National Institute of Technology\s+[A-Z][a-z]+)\b`.
4. **Repeated Runs Duplicate Records**:
   - *Issue*: Scouting the same directory twice duplicated rows in `professors`, `papers`, and `professor_papers`.
   - *Fix*: Added `find_professor_by_email`, `find_professor_by_name`, `find_paper_by_doi`, `find_paper_by_arxiv_id`, and `find_paper_by_title` in `ArtemisRepository`. In `_persist_professor_and_papers`, existing IDs and creation timestamps are preserved, updating records cleanly.
5. **Overstated Verification Labeling**:
   - *Issue*: Terminal output printed `[verified]` for emails, which users could misinterpret as deliverability verification.
   - *Fix*: Changed label to `[listed on official page; deliverability unverified]`, and paper matches to `[AFFILIATION MATCHED IN METADATA]` vs `[UNCERTAIN (Name-Only Match)]`.

---

## 3. Exact Test Results

### 3.1 Unit & Integration Test Suite

**Execution Command**:
```powershell
.\.venv\Scripts\pytest -v
```

**Output**:
```text
============================= test session starts =============================
platform win32 -- Python 3.10.9, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\PIYUSH\Desktop\ARTEMIS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\PIYUSH\Desktop\ARTEMIS
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 75 items

tests/test_cli.py (6 passed)
tests/test_crawler.py (9 passed)
tests/test_models.py (22 passed)
tests/test_repository.py (25 passed)
tests/test_scouting.py (11 passed)
tests/test_service.py (1 passed)
tests/test_smoke_real_web.py (1 skipped - requires RUN_LIVE_TESTS=1)

======================== 74 passed, 1 skipped in 0.47s ========================
```

### 3.2 Real-World Live Verification: IIT Delhi CSE

- **Target URL**: `https://homecse.iitd.ac.in/faculty/`
- **Page Layout**: WordPress Elementor (`div.single-team-area`)
- **Keywords**: `systems`, `algorithms`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m artemis scout https://homecse.iitd.ac.in/faculty/ -k "systems" "algorithms" -f 3 -p 2 --db artemis_iitd_live.db
  ```
- **Results**:
  - **Faculty Discovered**: 3 (S.N. Maheshwari, Amit Kumar, Aaditeshwar Seth)
  - **Emails Discovered**: 3 / 3 (`snm@cse.iitd.ac.in`, `amitk@cse.iitd.ac.in`, `aseth@cse.iitd.ac.in`)
  - **Profile Subpages Parsed**: 3 (`https://homecse.iitd.ac.in/team/...`)
  - **Papers Retrieved**: 6 papers from OpenAlex and arXiv
  - **Affiliation Grounding**:
    - Aaditeshwar Seth: 2 papers matched with `"Indian Institute of Technology Delhi"` metadata (`confidence: 1.00`).
    - Amit Kumar: 2 papers matched, 1 on arXiv (`confidence: 0.40 [UNCERTAIN]`, correctly recognizing missing affiliation metadata on preprint).
  - **Ground Truth Spot-Check**: Matches official directory records on `homecse.iitd.ac.in`.

### 3.3 Real-World Live Verification: IIT Madras CSE

- **Target URL**: `https://www.cse.iitm.ac.in/outerfaculty.php`
- **Page Layout**: Custom HTML5 card grid (`div.fac-card` with data attributes)
- **Keywords**: `cryptography`, `security`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m artemis scout https://www.cse.iitm.ac.in/outerfaculty.php -k "cryptography" "security" -f 3 -p 2 --db artemis_iitm_live.db
  ```
- **Results**:
  - **Faculty Discovered**: 3 (Aishwarya Thiruvengadam, Ashrujit Ghoshal, Chester Rebeiro)
  - **Emails Discovered**: 3 / 3 (successfully deobfuscated `[at]` and `[dot]` into `aishwarya@cse.iitm.ac.in`, `ashrujit@cse.iitm.ac.in`, `chester@cse.iitm.ac.in`)
  - **Links Discovered**: Profile links and personal/lab homepages (`https://sites.google.com/view/aishwaryat`, `https://cse.iitm.ac.in/~ashrujit/`, `https://cse.iitm.ac.in/~chester/`)
  - **Papers Retrieved**: 6 papers from OpenAlex and arXiv
  - **Affiliation Grounding**:
    - Aishwarya Thiruvengadam: Top paper confirmed with IIT Madras metadata (`confidence: 1.00`); earlier 2018 CCS paper from UC Santa Barbara postdoc correctly flagged as `[UNCERTAIN]` (`confidence: 0.40`).
    - Ashrujit Ghoshal: Both IEEE S&P and LNCS papers confirmed with IIT Madras metadata (`confidence: 1.00`).
    - Chester Rebeiro: Both IACR TCHES and arXiv papers confirmed with IIT Madras metadata (`confidence: 1.00`).

### 3.4 Client-Side SPA Handling: IIT Bombay CSE

- **Target URL**: `https://www.cse.iitb.ac.in/people/faculty.php`
- **Page Structure**: Client-side Angular Single Page Application (`<app-root></app-root>`)
- **Behavior**:
  - ARTEMIS detected empty Angular component root with no server-rendered text.
  - Raised `JavaScriptRenderedPageError` with clear diagnostic:
    ```text
    [ERROR] JavaScript-Rendered Directory Detected:
      Directory page 'https://www.cse.iitb.ac.in/people/faculty.php' requires client-side
      JavaScript execution (Single Page Application). ARTEMIS currently supports server-rendered
      HTML to prevent hallucination.
    ```
  - **Verification**: Zero fabricated data was generated.

### 3.5 Missing Emails Handling: IIT Kanpur CSE

- **Target URL**: `https://www.cse.iitk.ac.in/pages/Faculty.html`
- **Page Structure**: Bootstrap grid (`div.team-grid`) with names and titles, but no emails published on summary cards.
- **Behavior**:
  - 39 faculty members extracted.
  - Email addresses left as `None` with status `UNVERIFIED` / `[Not publicly listed on directory / unverified]`.
  - **Verification**: Zero fabricated or guessed emails were generated.

### 3.6 Idempotency Verification Across Repeated Runs

- **Command**: Ran `artemis scout https://www.cse.iitm.ac.in/outerfaculty.php -k "cryptography" -f 2 -p 2 --db artemis_test_idempotency.db` twice sequentially.
- **Run 1 Database State**: `professors=2, papers=4, links=4`
- **Run 2 Database State**: `professors=2, papers=4, links=4`
- **Result**: Zero duplicates created; existing entities updated cleanly.

---

## 4. Commands to Reproduce Verification Tests

### Run Full Pytest Suite
```powershell
.\.venv\Scripts\pytest -v
```

### Reproduce Live Test 1: IIT Delhi CSE
```powershell
.\.venv\Scripts\python.exe -m artemis scout https://homecse.iitd.ac.in/faculty/ -k "systems" "algorithms" -f 3 -p 2 --db artemis_iitd_live.db
```

### Reproduce Live Test 2: IIT Madras CSE
```powershell
.\.venv\Scripts\python.exe -m artemis scout https://www.cse.iitm.ac.in/outerfaculty.php -k "cryptography" "security" -f 3 -p 2 --db artemis_iitm_live.db
```

### Reproduce SPA Detection Test: IIT Bombay CSE
```powershell
.\.venv\Scripts\python.exe -m artemis scout https://www.cse.iitb.ac.in/people/faculty.php -k "systems"
```

---

## 5. Milestone 2 Completion Summary

- **Milestone 2 Status**: Completed and verified on real-world Indian institute faculty directories (IIT Delhi, IIT Madras, IIT Bombay, IIT Kanpur).
- **Test Baseline**: 74 unit tests passed, 1 skipped.

---

## 6. Milestone 3 Implementation & Verification Report

**Date**: October 25, 2026  
**Status**: Milestone 3 Complete & Fully Validated Offline  
**Test Suite**: 106 Unit Tests Passed (0 Failed, 1 Skipped — Live Web Smoke Test)  

### 6.1 What Was Implemented in Milestone 3

1. **Student Résumé Ingestion (`artemis.resume`)**:
   - `extract_text_from_file`: Robust extraction supporting `.pdf` (via `pypdf`), `.md`, and `.txt` with UTF-8 and Latin-1 fallbacks.
   - `parse_resume_evidence`: Heuristic extraction into structured `ResumeEvidence` models with `skills`, `key_achievements`, exact `raw_snippet`, and strict initial `UNVERIFIED` status (self-reported claims).
   - Skips contact headers and email addresses to avoid mistaking personal metadata for project titles.
2. **Replaceable LLM Interface (`artemis.llm`)**:
   - `LLMProvider` abstract interface with `generate()` and `generate_structured(schema: Type[T])`.
   - `MockLLMProvider`: Deterministic, offline heuristic generator capable of extracting paper titles, evidence IDs, and sender names from structured prompts. Enables zero-cost, network-free, reproducible testing.
   - `GeminiLLMProvider`: Lightweight REST client calling Google Generative Language API (`gemini-2.0-flash`) via `httpx` with `GEMINI_API_KEY`.
   - `get_llm_provider()`: Factory dynamically selecting provider based on `ARTEMIS_LLM_PROVIDER` environment variable.
3. **Research Brief Synthesis & Grounding Guardrails (`artemis.brief`)**:
   - `ResearchBriefSynthesizer`: Connects discovered papers with authentic student qualifications.
   - **Abstract-Only Safety**: When full paper manuscript is absent, brief headline is strictly prefixed with `[Abstract-Based Brief]` and methodology/limitations explicitly state derivation from abstract text. Prevents fabricating experimental benchmarks or participant numbers.
   - **Fabricated Claim Rejection**: Verifies returned `matched_evidence_ids` against genuine student evidence. Discards hallucinated IDs.
   - **Uncertainty Reflection**: When zero genuine evidence matches, forces confidence score `<= 0.35` and records explicit background gaps.
   - **Deterministic Fallback**: Automatically activates keyword-based heuristic fallback if LLM service fails or outputs malformed non-JSON text.
4. **Cold Outreach Email Draft Generator (`artemis.email`)**:
   - `DraftGenerator`: Connects brief and evidence to a single publication.
   - **Review-First Stance**: Status is set strictly to `draft_pending`. Emails are never sent automatically.
   - **Forbidden Phrase Filtering**: Scans and sanitizes fabricated prior interactions (`"as we discussed"`, `"enjoyed your class"`) or phantom openings (`"saw your posting"`).
   - **Recipient Email Safety**: If professor email is unverified or missing from the directory, generates a safe review placeholder and flags an explicit audit warning.
   - **Word Count Discipline**: Trims drafts exceeding 300 words to ensure respectful brevity.
5. **Database Schema & Migrations (`artemis.db`)**:
   - Updated `resume_evidence` table with `raw_snippet` and `verification_status`.
   - Updated `research_briefs` table with `limitations_json` and `gaps_json`.
   - Backward-compatible SQLite table migration checks added to `init_db`.
6. **CLI Subcommands & Pipeline (`artemis.cli`)**:
   - `artemis ingest-resume <file>`: Ingests résumé and persists evidence.
   - `artemis brief --prof <ID> --paper <ID>`: Synthesizes and displays research brief.
   - `artemis draft --prof <ID> --brief <ID> [--name SENDER_NAME]`: Generates formatted outreach draft.
   - `artemis match <URL> -r <FILE> -k <KEYWORDS...>`: Complete automated scouting, matching, and drafting pipeline.

---

### 6.2 Exact Pytest Results

**Execution Command**:
```powershell
.\.venv\Scripts\pytest -v
```

**Output**:
```text
============================= test session starts =============================
platform win32 -- Python 3.10.9, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\PIYUSH\Desktop\ARTEMIS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\PIYUSH\Desktop\ARTEMIS
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 107 items

tests/test_brief_synthesizer.py (4 passed)
tests/test_cli.py (6 passed)
tests/test_crawler.py (9 passed)
tests/test_email_generator.py (4 passed)
tests/test_llm.py (11 passed)
tests/test_milestone3_service_and_cli.py (5 passed)
tests/test_models.py (22 passed)
tests/test_repository.py (25 passed)
tests/test_resume.py (8 passed)
tests/test_scouting.py (11 passed)
tests/test_service.py (1 passed)
tests/test_smoke_real_web.py (1 skipped - requires RUN_LIVE_TESTS=1)

======================= 106 passed, 1 skipped in 0.99s ========================
```

---

### 6.3 Anti-Hallucination & Grounding Guardrails Verification Matrix

| Risk / Failure Mode | Safety Guardrail in Code | Test Verification |
|---|---|---|
| **Hallucinated Paper Methodology** | Abstract-only papers are strictly tagged `[Abstract-Based Brief]`. Methodology must note abstract origin. | `test_synthesize_abstract_only_paper_enforces_labeling` |
| **Hallucinated Student Evidence IDs** | `_apply_grounding_guardrails` verifies all returned IDs against ingested `valid_evidence_map`. Fabricated IDs are stripped. | `test_reject_fabricated_evidence_ids` |
| **Overconfident Matching on Unrelated Evidence** | When zero genuine evidence items match, confidence is forced to `<= 0.35` and background gaps are populated. | `test_missing_or_unrelated_evidence_returns_uncertainty` |
| **Malformed LLM Output / Non-JSON** | `_deterministic_fallback_synthesis` keyword matcher generates grounded brief without crashing. | `test_deterministic_fallback_on_malformed_llm_json` |
| **Invented Prior Relationships or Openings** | `FORBIDDEN_PHRASES` regex filters out "as we discussed", "saw your posting", etc. | `test_forbids_hallucinated_prior_contact_phrases` |
| **Unverified Professor Email** | Flags audit warning and uses safe placeholder to prevent accidental blind sending. | `test_unverified_missing_email_generates_safety_warning` |
| **Automated Email Transmission** | Draft status is strictly `draft_pending`. No SMTP or external sending mechanism exists. | `test_synthesize_brief_and_generate_draft_end_to_end` |

---

### 6.4 Commands to Reproduce Milestone 3 Verification

#### 1. Run Complete Pytest Suite
```powershell
.\.venv\Scripts\pytest -v
```

#### 2. Run Résumé Ingestion CLI
```powershell
.\.venv\Scripts\python.exe -m artemis ingest-resume tests/fixtures/sample_resume.md --db test.db
```

#### 3. Run End-to-End Synthesis and Drafting
```powershell
.\.venv\Scripts\python.exe -m artemis match https://www.cse.iitm.ac.in/outerfaculty.php -r ./my_resume.md -k "systems" "security" -f 2 --name "Student Researcher"
```

---

## 7. System Readiness for Milestone 4

### Verdict: **READY FOR MILESTONE 4**

Milestone 3 is complete, fully tested, and resilient against hallucination. The SQLite database reliably persists student qualifications, professor profiles, publications, research briefs, and outreach drafts.

### Scope for Milestone 4 (Personalized Outreach & Gmail Draft Sync):
1. **Google OAuth 2.0 Client**:
   - Secure local flow with `credentials.json` and persistent token storage.
   - Minimal Gmail scope (`https://www.googleapis.com/auth/gmail.compose`): **draft creation only, strictly prohibiting sending (`gmail.send`)**.
2. **Gmail API Draft Creator**:
   - Convert `EmailDraft` (with status `draft_pending`) into a native Gmail draft.
   - Store the resulting Gmail draft ID in `gmail_draft_id` and update status to `gmail_synced`.
3. **CLI Command**:
   - `artemis sync-gmail [--draft-id DRAFT_ID] [--db DB_PATH]` with clear confirmation and safety prompts.
