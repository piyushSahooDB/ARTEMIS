"""Section A: Overview Dashboard for A.R.T.E.M.I.S."""

from typing import Optional

import streamlit as st

from artemis.ui.state import get_repository


def render_dashboard() -> None:
    """Render the main system overview dashboard."""
    repo = get_repository()

    st.markdown("## 📊 Research Intelligence Overview")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Real-time pipeline metrics, scouting activity, and outreach readiness."
        "</p>",
        unsafe_allow_html=True,
    )

    # 1. Fetch real counts from SQLite database
    professors = repo.list_professors()
    papers = repo.list_papers()
    briefs = repo.list_briefs()
    drafts = repo.list_drafts()
    scouting_runs = repo.list_scouting_runs(limit=10)

    pending_drafts = [d for d in drafts if getattr(d, "status", "") == "draft_pending"]

    # 2. Key Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="artemis-metric-card">
                <div class="artemis-metric-label">Discovered Faculty</div>
                <div class="artemis-metric-val">{len(professors)}</div>
                <div style="font-size: 0.75rem; color: #8b949e;">Verified directories</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="artemis-metric-card">
                <div class="artemis-metric-label">Tracked Papers</div>
                <div class="artemis-metric-val">{len(papers)}</div>
                <div style="font-size: 0.75rem; color: #8b949e;">OpenAlex & arXiv</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="artemis-metric-card">
                <div class="artemis-metric-label">Research Briefs</div>
                <div class="artemis-metric-val">{len(briefs)}</div>
                <div style="font-size: 0.75rem; color: #8b949e;">Evidence-grounded</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="artemis-metric-card">
                <div class="artemis-metric-label">Pending Drafts</div>
                <div class="artemis-metric-val">{len(pending_drafts)}</div>
                <div style="font-size: 0.75rem; color: #8b949e;">Ready for review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

    # 3. Scouting Runs Section
    st.markdown("### 🛰️ Recent Scouting Runs")
    if not scouting_runs:
        st.info("No scouting runs recorded yet in the database. Use **Research Scout** in the sidebar to run your first faculty discovery session.")
    else:
        run_data = []
        for r in scouting_runs:
            status_badge = (
                f"<span class='artemis-badge badge-verified'>{r.status.upper()}</span>"
                if r.status == "completed"
                else f"<span class='artemis-badge badge-danger'>{r.status.upper()}</span>"
            )
            kw_str = ", ".join(r.keywords) if r.keywords else "—"
            err_str = f" <span style='color: #f85149;'>({r.error_message})</span>" if r.error_message else ""
            run_data.append({
                "Date": r.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(r.created_at, "strftime") else str(r.created_at)[:16],
                "Directory URL": r.directory_url,
                "Keywords": kw_str,
                "Faculty": r.faculty_found,
                "Papers": r.papers_found,
                "Status": r.status.capitalize(),
                "Error": r.error_message or "None",
            })
        st.dataframe(run_data, use_container_width=True)

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

    # 4. Two Columns: Discovered Faculty & Tracked Papers
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 🎓 Recently Discovered Faculty")
        if not professors:
            st.markdown(
                """
                <div class="artemis-card">
                    <p style="color: #8b949e; margin: 0;">No professors found in database yet.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            recent_profs = professors[:5]
            for p in recent_profs:
                email_badge = (
                    f"<span class='artemis-badge badge-verified'>Email: {p.email}</span>"
                    if p.email
                    else "<span class='artemis-badge badge-neutral'>No Email Listed</span>"
                )
                inst = p.institution or "Unknown Institution"
                dept = p.department or "Department not specified"
                interests_str = ", ".join(p.research_interests[:3]) if p.research_interests else "General research"
                st.markdown(
                    f"""
                    <div class="artemis-card" style="margin-bottom: 12px; padding: 12px 16px;">
                        <div style="font-weight: 600; font-size: 1.05rem; color: #f0f6fc;">
                            {p.name} <span style="font-size: 0.8rem; font-weight: 400; color: #8b949e;">— {p.designation or 'Faculty'}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #8b949e; margin: 4px 0;">
                            {dept}, {inst}
                        </div>
                        <div style="font-size: 0.82rem; color: #c9d1d9; margin-bottom: 6px;">
                            <strong>Interests:</strong> {interests_str}
                        </div>
                        <div>{email_badge}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with c2:
        st.markdown("### 📑 Recently Tracked Papers")
        if not papers:
            st.markdown(
                """
                <div class="artemis-card">
                    <p style="color: #8b949e; margin: 0;">No papers tracked in database yet.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            recent_papers = papers[:5]
            for paper in recent_papers:
                year_str = str(paper.year) if paper.year else "N/D"
                authors_str = ", ".join(paper.authors[:2]) + (" et al." if len(paper.authors) > 2 else "")
                doi_or_url = paper.doi or paper.url or "No URL"
                score_str = f"Score: {paper.match_score:.1f}" if paper.match_score else ""
                st.markdown(
                    f"""
                    <div class="artemis-card" style="margin-bottom: 12px; padding: 12px 16px;">
                        <div style="font-weight: 600; font-size: 0.95rem; color: #58a6ff; line-height: 1.3;">
                            {paper.title}
                        </div>
                        <div style="font-size: 0.82rem; color: #8b949e; margin: 4px 0;">
                            {authors_str} ({year_str})
                        </div>
                        <div style="font-size: 0.8rem; color: #e6af2e;">
                            {score_str} <span style="color: #8b949e; margin-left: 8px;">[{paper.source_type}]</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
