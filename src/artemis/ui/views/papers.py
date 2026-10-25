"""Section D: Paper Explorer interface."""

import streamlit as st

from artemis.ui.state import get_repository


def render_papers() -> None:
    """Render the Paper Explorer view with search, filtering, and bibliographic metadata."""
    repo = get_repository()

    st.markdown("## 📑 Paper Explorer")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Browse discovered research papers from OpenAlex and arXiv with explicit author match confidence and provenance."
        "</p>",
        unsafe_allow_html=True,
    )

    all_papers = repo.list_papers()

    if not all_papers:
        st.info("No papers stored in database yet. Run a discovery session in **Research Scout** first.")
        return

    # Filter Bar
    c_search, c_src, c_score = st.columns([3, 2, 2])
    with c_search:
        search_query = st.text_input("🔍 Search Papers", placeholder="Search title, authors, or abstract...")
    with c_src:
        sources = list(set(p.source_type for p in all_papers if p.source_type))
        source_filter = st.selectbox("Source Platform", options=["All"] + sorted(sources))
    with c_score:
        min_score = st.slider("Min Match Score", min_value=0.0, max_value=1.0, value=0.0, step=0.1)

    # Filter logic
    filtered = all_papers
    if search_query:
        q = search_query.lower()
        filtered = [
            p for p in filtered
            if q in p.title.lower()
            or any(q in a.lower() for a in p.authors)
            or (p.abstract and q in p.abstract.lower())
        ]

    if source_filter != "All":
        filtered = [p for p in filtered if p.source_type == source_filter]

    if min_score > 0.0:
        filtered = [p for p in filtered if (p.match_score or 0.0) >= min_score]

    st.markdown(f"**Showing {len(filtered)} of {len(all_papers)} papers**")

    # Render Paper Cards
    for paper in filtered:
        # Check affiliated professor
        prof = repo.get_professor(paper.professor_id) if paper.professor_id else None
        
        with st.expander(f"{paper.title} ({paper.year or 'N/A'})", expanded=False):
            st.markdown(
                f"""
                <div style="font-size: 1.15rem; font-weight: 700; color: #58a6ff; margin-bottom: 6px;">
                    {paper.title}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Metadata Row
            authors_str = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
            venue_str = f" | <strong>Venue:</strong> {paper.venue}" if paper.venue else ""
            st.markdown(
                f"""
                <div style="font-size: 0.88rem; color: #8b949e; margin-bottom: 8px;">
                    <strong>Authors:</strong> {authors_str}<br>
                    <strong>Year:</strong> {paper.year or 'N/A'}{venue_str} | 
                    <strong>Source:</strong> <span class='artemis-badge badge-neutral'>{paper.source_type}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Identity & Verification Breakdown
            col_id, col_prov = st.columns(2)
            with col_id:
                if prof:
                    ver_text = (
                        "<span class='artemis-badge badge-verified'>Affiliation Verified</span>"
                        if getattr(paper, "author_verified", False)
                        else "<span class='artemis-badge badge-unverified'>Name-Only Match (Uncertain)</span>"
                    )
                    st.markdown(
                        f"""
                        <div style="font-size: 0.85rem; margin-bottom: 8px;">
                            <strong>Associated Faculty:</strong> {prof.name} ({prof.institution or 'Institute'})<br>
                            <strong>Author Link:</strong> {ver_text}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown("<div style='font-size: 0.85rem; color: #8b949e;'>No faculty directly linked.</div>", unsafe_allow_html=True)

            with col_prov:
                score_val = f"{paper.match_score * 100:.0f}%" if paper.match_score else "N/A"
                st.markdown(
                    f"""
                    <div style="font-size: 0.85rem; margin-bottom: 8px;">
                        <strong>Keyword Relevance Score:</strong> <span style="color: #e6af2e; font-weight: 600;">{score_val}</span><br>
                        <strong>Identifier:</strong> <code>{paper.id}</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Persistent URLs
            st.markdown("##### 🔗 Persistent Links")
            links_rendered = False
            if paper.doi:
                doi_url = f"https://doi.org/{paper.doi}" if not paper.doi.startswith("http") else paper.doi
                st.markdown(f"- **DOI:** [{paper.doi}]({doi_url})")
                links_rendered = True
            if paper.arxiv_id:
                arxiv_url = f"https://arxiv.org/abs/{paper.arxiv_id}"
                st.markdown(f"- **arXiv:** [{paper.arxiv_id}]({arxiv_url})")
                links_rendered = True
            if paper.url and not links_rendered:
                st.markdown(f"- **Paper URL:** [{paper.url}]({paper.url})")
                links_rendered = True
            if not links_rendered:
                st.markdown("- *No external URL recorded.*")

            # Abstract Section with explicit guardrail badge
            st.markdown("##### 📄 Abstract")
            if paper.abstract:
                st.markdown(
                    f"""
                    <div style="margin-bottom: 6px;">
                        <span class="artemis-badge badge-abstract">Abstract-Only Available</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #c9d1d9; background: #0d1117; padding: 12px; border-radius: 6px; border: 1px solid #30363d; line-height: 1.5;">
                        {paper.abstract}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="font-size: 0.88rem; color: #8b949e; font-style: italic;">
                        No abstract available from upstream repository.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Quick Action
            if prof:
                if st.button(f"🎯 Create Brief for this Paper", key=f"btn_paper_brief_{paper.id}"):
                    st.session_state["selected_professor_id"] = prof.id
                    st.session_state["selected_paper_id"] = paper.id
                    st.session_state["current_view"] = "Research Brief Workspace"
                    st.rerun()
