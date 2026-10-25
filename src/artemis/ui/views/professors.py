"""Section C: Professor Explorer interface."""

import streamlit as st

from artemis.ui.state import get_repository


def render_professors() -> None:
    """Render the Professor Explorer view with search, filtering, and detail inspect."""
    repo = get_repository()

    st.markdown("## 🎓 Professor Explorer")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Inspect verified faculty profiles, institutional affiliations, deliverability badges, and associated research papers."
        "</p>",
        unsafe_allow_html=True,
    )

    all_professors = repo.list_professors()

    if not all_professors:
        st.info("No professors stored in database yet. Run a discovery session in **Research Scout** first.")
        return

    # Filter Bar
    c_search, c_email, c_sort = st.columns([3, 2, 2])
    with c_search:
        search_query = st.text_input("🔍 Search Faculty", placeholder="Search by name, department, or keyword...")
    with c_email:
        email_filter = st.selectbox(
            "Email Status",
            options=["All", "With Email Only", "Verified Email Only", "No Email Listed"],
        )
    with c_sort:
        sort_by = st.selectbox(
            "Sort By",
            options=["Name (A-Z)", "Match Score (High to Low)"],
        )

    # Filter logic
    filtered = all_professors
    if search_query:
        q = search_query.lower()
        filtered = [
            p for p in filtered
            if q in p.name.lower()
            or (p.department and q in p.department.lower())
            or (p.institution and q in p.institution.lower())
            or any(q in kw.lower() for kw in p.research_interests)
        ]

    if email_filter == "With Email Only":
        filtered = [p for p in filtered if p.email]
    elif email_filter == "Verified Email Only":
        filtered = [p for p in filtered if p.email and getattr(p, "email_verification_status", "") == "verified"]
    elif email_filter == "No Email Listed":
        filtered = [p for p in filtered if not p.email]

    if sort_by == "Name (A-Z)":
        filtered.sort(key=lambda p: p.name.lower())
    elif sort_by == "Match Score (High to Low)":
        filtered.sort(key=lambda p: (getattr(p, "match_score", 0.0) or 0.0), reverse=True)

    st.markdown(f"**Showing {len(filtered)} of {len(all_professors)} faculty members**")

    # Render Professor Cards
    for prof in filtered:
        papers = repo.get_papers_by_professor(prof.id)
        
        # Email badge
        if prof.email:
            ver_status = getattr(prof, "email_verification_status", "unverified")
            if ver_status == "verified":
                email_badge = f"<span class='artemis-badge badge-verified'>✓ Verified: {prof.email}</span>"
            else:
                email_badge = f"<span class='artemis-badge badge-unverified'>⚠ Scraped: {prof.email}</span>"
        else:
            email_badge = "<span class='artemis-badge badge-neutral'>No Email Listed</span>"

        interests_str = ", ".join(prof.research_interests) if prof.research_interests else "General research"

        with st.expander(f"{prof.name} — {prof.institution or 'Unknown Institute'} ({len(papers)} papers)", expanded=False):
            st.markdown(
                f"""
                <div style="font-size: 1.15rem; font-weight: 700; color: #f0f6fc; margin-bottom: 4px;">
                    {prof.name}
                </div>
                <div style="font-size: 0.9rem; color: #8b949e; margin-bottom: 8px;">
                    <strong>Designation:</strong> {prof.designation or 'Faculty Member'} | 
                    <strong>Department:</strong> {prof.department or 'N/A'} | 
                    <strong>Institution:</strong> {prof.institution or 'N/A'}
                </div>
                <div style="margin-bottom: 8px;">
                    {email_badge}
                    <span class='artemis-badge badge-gold'>Confidence: {getattr(prof, 'confidence_score', 0.8) * 100:.0f}%</span>
                </div>
                <div style="font-size: 0.9rem; color: #c9d1d9; margin-bottom: 12px;">
                    <strong>Research Focus:</strong> {interests_str}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Profile URLs & Provenance
            st.markdown("##### 🔗 Verified Links & Provenance")
            col_links, col_prov = st.columns(2)
            with col_links:
                if prof.profile_url:
                    st.markdown(f"- **Faculty Profile:** [{prof.profile_url}]({prof.profile_url})")
                if prof.lab_url:
                    st.markdown(f"- **Lab Website:** [{prof.lab_url}]({prof.lab_url})")
                if prof.google_scholar_url:
                    st.markdown(f"- **Google Scholar:** [{prof.google_scholar_url}]({prof.google_scholar_url})")
                if not (prof.profile_url or prof.lab_url or prof.google_scholar_url):
                    st.markdown("- *No external profile links extracted.*")

            with col_prov:
                source_url = getattr(prof, "source_url", None)
                if source_url:
                    st.markdown(f"- **Extracted From:** [{source_url}]({source_url})")
                st.markdown(f"- **Record ID:** `{prof.id}`")

            # Associated Papers
            st.markdown(f"##### 📑 Associated Papers ({len(papers)})")
            if not papers:
                st.info("No papers tracked for this researcher yet.")
            else:
                for paper in papers:
                    p_score = f"(Score: {paper.match_score:.1f})" if paper.match_score else ""
                    st.markdown(
                        f"""
                        <div class="artemis-card" style="margin-bottom: 8px; padding: 10px 14px;">
                            <div style="font-weight: 600; color: #58a6ff; font-size: 0.95rem;">
                                {paper.title} <span style="font-size: 0.8rem; color: #e6af2e;">{p_score}</span>
                            </div>
                            <div style="font-size: 0.8rem; color: #8b949e; margin: 2px 0;">
                                {', '.join(paper.authors[:3])} ({paper.year or 'N/A'}) — <em>{paper.source_type}</em>
                            </div>
                            <div style="font-size: 0.82rem; color: #c9d1d9;">
                                {paper.abstract[:180] + '...' if paper.abstract else 'No abstract available.'}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # Quick Action
            if papers:
                if st.button(f"🎯 Synthesize Brief with {prof.name}", key=f"btn_brief_{prof.id}"):
                    st.session_state["selected_professor_id"] = prof.id
                    st.session_state["selected_paper_id"] = papers[0].id
                    st.session_state["current_view"] = "Research Brief Workspace"
                    st.rerun()
