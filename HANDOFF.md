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

## 5. System Readiness for Milestone 3

### Verdict: **READY FOR MILESTONE 3**

The faculty discovery and academic paper scouting pipeline is robust, polite, truthful, and verified against diverse real-world Indian university websites.

### Smallest Recommended Next Step for Milestone 3:
1. **Student Résumé Evidence Ingestion**:
   - Provide a clean interface to import student résumé facts (projects, skills, coursework) as `ResumeEvidence` models with category, achievements, and self-reported verification status.
2. **Replaceable LLM Provider Interface**:
   - Define an abstract `LLMProvider` protocol (supporting Google Gemini or local LLM) with a mock provider for zero-cost offline pytest execution.
3. **Research Brief Synthesis**:
   - Synthesize `ResearchBrief` objects connecting a discovered paper's core contributions with the student's authentic résumé evidence, strictly forbidding hallucinated student qualifications or fabricated paper conclusions.
