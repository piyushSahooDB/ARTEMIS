"""Section G: Settings & System Status interface."""

import os
import subprocess
import sys

import streamlit as st

from artemis.crawler.client import PoliteHttpClient, get_default_user_agent
from artemis.ui.state import get_db_path, get_repository, set_db_path


def _get_git_commit() -> str:
    """Safely obtain current git commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip() or "Unknown"
    except Exception:
        return "Unknown"


def render_settings() -> None:
    """Render system diagnostics, database configuration, and LLM provider status."""
    st.markdown("## ⚙️ Settings & System Status")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Database connections, LLM provider configuration, crawler user agent, and operational diagnostics."
        "</p>",
        unsafe_allow_html=True,
    )

    repo = get_repository()
    db_path = get_db_path()

    # 1. Database Configuration
    st.markdown("### 🗄️ Database & Storage")
    c_db1, c_db2 = st.columns([3, 1])
    with c_db1:
        new_db_path = st.text_input("Active SQLite Database Path", value=db_path)
    with c_db2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("Apply DB Path", use_container_width=True):
            if new_db_path.strip() != db_path:
                set_db_path(new_db_path.strip())
                st.success(f"Database switched to {new_db_path}!")
                st.rerun()

    # Connectivity Check & Record Counts
    try:
        prof_count = len(repo.list_professors())
        paper_count = len(repo.list_papers())
        brief_count = len(repo.list_briefs())
        draft_count = len(repo.list_drafts())
        ev_count = len(repo.list_evidence())
        runs_count = len(repo.list_scouting_runs())
        db_status_badge = "<span class='artemis-badge badge-verified'>✓ CONNECTED</span>"
    except Exception as e:
        db_status_badge = f"<span class='artemis-badge badge-danger'>ERROR: {e}</span>"
        prof_count = paper_count = brief_count = draft_count = ev_count = runs_count = 0

    st.markdown(
        f"""
        <div class="artemis-card">
            <div style="margin-bottom: 6px;">Status: {db_status_badge}</div>
            <div style="font-size: 0.88rem; color: #8b949e;">
                <strong>Database File:</strong> <code>{os.path.abspath(db_path)}</code>
            </div>
            <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 10px;">
                <span class="artemis-badge badge-neutral">Professors: {prof_count}</span>
                <span class="artemis-badge badge-neutral">Papers: {paper_count}</span>
                <span class="artemis-badge badge-neutral">Briefs: {brief_count}</span>
                <span class="artemis-badge badge-neutral">Drafts: {draft_count}</span>
                <span class="artemis-badge badge-neutral">Résumé Evidence: {ev_count}</span>
                <span class="artemis-badge badge-neutral">Scouting Runs: {runs_count}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. LLM Provider Configuration
    st.markdown("### 🤖 LLM Provider Interface")
    active_provider = os.getenv("ARTEMIS_LLM_PROVIDER", "mock").lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if active_provider == "gemini":
        prov_status = "<span class='artemis-badge badge-gold'>ACTIVE: GEMINI API</span>"
    else:
        prov_status = "<span class='artemis-badge badge-neutral'>ACTIVE: MOCK (DETERMINISTIC)</span>"

    key_status = (
        f"Configured (<code>{gemini_key[:6]}...****</code>)"
        if gemini_key
        else "<span style='color: #e3b341;'>Not set in environment (using mock provider)</span>"
    )

    st.markdown(
        f"""
        <div class="artemis-card">
            <div style="margin-bottom: 8px;">{prov_status}</div>
            <div style="font-size: 0.88rem; color: #8b949e; line-height: 1.6;">
                <strong>Active Mode:</strong> <code>{active_provider}</code><br>
                <strong>GEMINI_API_KEY:</strong> {key_status}<br>
                <strong>Provider Swapping:</strong> Configurable via <code>.env</code> file (<code>ARTEMIS_LLM_PROVIDER=gemini</code>).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Crawler & Politeness Configuration
    st.markdown("### 🕷️ Crawler Identification & Politeness")
    user_agent = get_default_user_agent()
    st.markdown(
        f"""
        <div class="artemis-card">
            <div style="font-size: 0.88rem; color: #8b949e; line-height: 1.6;">
                <strong>HTTP User-Agent:</strong><br>
                <code>{user_agent}</code><br><br>
                <strong>Politeness Delay:</strong> 0.5s between requests<br>
                <strong>HTTP Timeout:</strong> 10.0s<br>
                <strong>Robots Compliance:</strong> Respects <code>robots.txt</code> crawl-delay and disallow directives.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. Environment & Launch Instructions
    st.markdown("### 💻 Environment & Launch Diagnostics")
    git_hash = _get_git_commit()
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    st.markdown(
        f"""
        <div class="artemis-card">
            <div style="font-size: 0.88rem; color: #8b949e; line-height: 1.6;">
                <strong>Git Commit:</strong> <code>{git_hash}</code><br>
                <strong>Python Version:</strong> <code>{py_ver}</code> ({sys.platform})<br>
                <strong>Local Binding:</strong> <code>localhost:8501</code> (Strictly local, no public exposure)<br>
            </div>
            <div style="margin-top: 12px; font-size: 0.85rem; color: #c9d1d9;">
                <strong>How to Launch:</strong><br>
                <code>streamlit run app.py</code><br><br>
                <strong>How to Stop:</strong><br>
                Press <code>Ctrl+C</code> in the terminal session running Streamlit.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
