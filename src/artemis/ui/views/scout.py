"""Section B: Research Scout interface for faculty discovery and paper retrieval."""

from typing import List

import streamlit as st

from artemis.ui.state import get_repository, get_service


def render_scout() -> None:
    """Render the Research Scout search, crawl, and paper retrieval workspace."""
    repo = get_repository()
    service = get_service()

    st.markdown("## 🛰️ Research Scout")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Crawl public institute faculty directories, extract verified profiles, and discover matching academic publications."
        "</p>",
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️ Scouting Guide & Institute Directory Tips", expanded=False):
        st.markdown(
            """
            - **URL Selection**: Provide a direct public HTML faculty directory (e.g. `https://homecse.iitd.ac.in/faculty/`).
            - **Politeness**: A.R.T.E.M.I.S. respects `robots.txt`, identifies itself with a transparent user agent, and enforces request delays.
            - **Anti-Hallucination**: Faculty details are extracted strictly from public HTML. Names, emails, and profile links are never fabricated.
            - **Academic APIs**: Discovered researchers are queried against OpenAlex and arXiv. Papers without verifiable author links remain marked unverified.
            """
        )

    # Input Form
    with st.form(key="scout_form"):
        col_url, col_kw = st.columns([3, 2])
        with col_url:
            directory_url = st.text_input(
                "Institute Faculty Directory URL",
                value="https://homecse.iitd.ac.in/faculty/",
                placeholder="https://institute.ac.in/department/faculty",
                help="Direct URL to a university or institute department faculty listing.",
            )
        with col_kw:
            keywords_input = st.text_input(
                "Research Keywords (comma-separated)",
                value="algorithms, graph theory, compilers, distributed systems",
                placeholder="e.g. machine learning, robotics, NLP",
                help="Topics and keywords used to match faculty interests and query academic papers.",
            )

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            max_faculty = st.slider(
                "Max Faculty to Process",
                min_value=1,
                max_value=30,
                value=5,
                step=1,
                help="Limits crawling bounded page count for safety and polite scraping.",
            )
        with col_opt2:
            max_papers = st.slider(
                "Max Papers per Discovered Researcher",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                help="Limits OpenAlex/arXiv paper search per faculty member.",
            )

        submit_scout = st.form_submit_button("🚀 Run Research Scout", use_container_width=True)

    if submit_scout:
        if not directory_url or not directory_url.strip():
            st.error("Please enter a valid directory URL.")
            return

        keywords: List[str] = [k.strip() for k in keywords_input.split(",") if k.strip()]
        if not keywords:
            st.warning("No keywords specified. Scouting will search for general publications.")

        progress_msg = st.empty()
        progress_msg.info(f"Connecting to **{directory_url}** and executing polite crawler...")

        try:
            with st.spinner("Scouting faculty directory and fetching academic publications..."):
                result = service.scout(
                    directory_url=directory_url.strip(),
                    keywords=keywords,
                    max_faculty=max_faculty,
                    max_papers_per_faculty=max_papers,
                    persist=True,
                )

            progress_msg.empty()
            st.success(
                f"🎉 Scouting Complete! Discovered **{len(result.professors)}** faculty members and **{len(result.papers)}** matching papers."
            )

            # Display Run Metrics
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Discovered Faculty", len(result.professors))
            with c2:
                st.metric("Matched Papers", len(result.papers))

            # Display discovered professors in cards
            if result.professors:
                st.markdown("### 🎓 Discovered Faculty")
                for prof in result.professors:
                    email_badge = (
                        f"<span class='artemis-badge badge-verified'>Email: {prof.email}</span>"
                        if prof.email
                        else "<span class='artemis-badge badge-neutral'>No Email Listed</span>"
                    )
                    interests = ", ".join(prof.research_interests) if prof.research_interests else "Not specified"
                    st.markdown(
                        f"""
                        <div class="artemis-card">
                            <div style="font-weight: 600; font-size: 1.1rem; color: #f0f6fc;">
                                {prof.name} <span style="font-size: 0.85rem; font-weight: 400; color: #8b949e;">({prof.designation or 'Faculty'})</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #8b949e; margin: 4px 0;">
                                {prof.department or 'Dept'}, {prof.institution or 'Institute'}
                            </div>
                            <div style="font-size: 0.85rem; color: #c9d1d9; margin: 6px 0;">
                                <strong>Research Interests:</strong> {interests}
                            </div>
                            <div style="margin-top: 8px;">
                                {email_badge}
                                <a href="{prof.profile_url}" target="_blank" style="color: #e6af2e; font-size: 0.8rem; margin-left: 8px;">
                                    View Official Profile ↗
                                </a>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            if result.papers:
                st.markdown("### 📑 Discovered Papers")
                for p in result.papers:
                    score_str = f"Match Score: {p.match_score:.1f}" if p.match_score else ""
                    st.markdown(
                        f"""
                        <div class="artemis-card">
                            <div style="font-weight: 600; font-size: 1rem; color: #58a6ff;">
                                {p.title}
                            </div>
                            <div style="font-size: 0.85rem; color: #8b949e; margin: 4px 0;">
                                Authors: {', '.join(p.authors[:3])} | Year: {p.year or 'N/A'} | Source: {p.source_type}
                            </div>
                            <div style="font-size: 0.82rem; color: #e6af2e; margin-bottom: 4px;">
                                {score_str}
                            </div>
                            <div style="font-size: 0.85rem; color: #c9d1d9;">
                                {p.abstract[:200] + '...' if p.abstract else '<em>No abstract available.</em>'}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        except Exception as e:
            progress_msg.empty()
            st.error(f"❌ Scouting Error: {e}")
            st.markdown(
                """
                > [!WARNING]
                > If this institute directory requires JavaScript or blocks standard HTTP clients,
                > A.R.T.E.M.I.S. reports this honestly rather than hallucinating faculty records.
                """
            )
