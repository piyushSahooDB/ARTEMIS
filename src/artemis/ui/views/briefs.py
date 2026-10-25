"""Section E: Research Brief Workspace interface."""

import streamlit as st

from artemis.brief.synthesizer import ResearchBriefSynthesizer
from artemis.email.generator import DraftGenerator
from artemis.ui.state import get_active_llm_provider, get_repository


def render_briefs() -> None:
    """Render the Research Brief workspace with synthesis, grounding badges, and evidence alignment."""
    repo = get_repository()

    st.markdown("## 🧠 Research Brief Workspace")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Synthesize evidence-grounded research briefs connecting discovered papers to verified student qualifications."
        "</p>",
        unsafe_allow_html=True,
    )

    professors = repo.list_professors()
    if not professors:
        st.info("No professors available. Scout an institute faculty directory first.")
        return

    # 1. Selection Controls
    col_prof, col_paper = st.columns(2)

    # Preselection handling from other views
    preselected_prof_id = st.session_state.get("selected_professor_id")
    prof_index = 0
    if preselected_prof_id:
        for idx, p in enumerate(professors):
            if p.id == preselected_prof_id:
                prof_index = idx
                break

    with col_prof:
        selected_prof = st.selectbox(
            "Select Faculty Member",
            options=professors,
            index=prof_index,
            format_func=lambda p: f"{p.name} ({p.institution or 'Unknown Institute'})",
        )

    # Load papers for selected professor
    papers = repo.get_papers_by_professor(selected_prof.id)
    if not papers:
        st.warning(f"No papers tracked for **{selected_prof.name}**. Scout more papers or select another faculty member.")
        return

    preselected_paper_id = st.session_state.get("selected_paper_id")
    paper_index = 0
    if preselected_paper_id:
        for idx, p in enumerate(papers):
            if p.id == preselected_paper_id:
                paper_index = idx
                break

    with col_paper:
        selected_paper = st.selectbox(
            "Select Associated Paper",
            options=papers,
            index=paper_index,
            format_func=lambda p: f"{p.title[:65]}... ({p.year or 'N/A'})",
        )

    # 2. Check for existing brief in repository
    existing_briefs = [
        b for b in repo.list_briefs_by_professor(selected_prof.id)
        if b.paper_id == selected_paper.id
    ]

    active_brief = existing_briefs[0] if existing_briefs else None

    # Résumé evidence check
    evidence_items = repo.list_evidence()

    st.markdown("---")

    # Synthesis Action Bar
    c_btn, c_info = st.columns([2, 4])
    with c_btn:
        generate_label = "⚡ Re-Synthesize Brief" if active_brief else "⚡ Synthesize Research Brief"
        synthesize_btn = st.button(generate_label, type="primary", use_container_width=True)

    with c_info:
        if not evidence_items:
            st.caption("⚠️ No student résumé evidence stored in database. Synthesizer will note evidence absence honestly.")
        else:
            st.caption(f"✓ Using {len(evidence_items)} verified student résumé evidence records for grounded matching.")

    if synthesize_btn:
        with st.spinner("Synthesizing grounded research brief via configured LLM provider..."):
            try:
                llm = get_active_llm_provider()
                synthesizer = ResearchBriefSynthesizer(llm_provider=llm)
                brief = synthesizer.synthesize(
                    professor=selected_prof,
                    paper=selected_paper,
                    evidence=evidence_items,
                    full_text=None,  # Abstract-only mode for academic discovery safety
                )
                repo.create_brief(brief)
                active_brief = brief
                st.success("✅ Research Brief synthesized and saved to database!")
            except Exception as e:
                st.error(f"Failed to synthesize brief: {e}")

    # 3. Render Brief
    if not active_brief:
        st.info("No brief generated yet for this paper. Click **Synthesize Research Brief** above to generate one.")
        return

    # Prominent Header Badges
    abstract_badge = (
        "<span class='artemis-badge badge-abstract'>[Abstract-Based Brief]</span>"
        if getattr(active_brief, "is_abstract_only", True)
        else "<span class='artemis-badge badge-verified'>[Full-Text Brief]</span>"
    )
    conf_score = getattr(active_brief, "alignment_confidence", 0.8) * 100
    conf_badge = f"<span class='artemis-badge badge-gold'>{conf_score:.0f}% Alignment Confidence</span>"

    st.markdown(
        f"""
        <div class="artemis-card">
            <div style="margin-bottom: 8px;">
                {abstract_badge}
                {conf_badge}
            </div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #f0f6fc; margin-bottom: 4px;">
                Research Brief: {selected_paper.title}
            </div>
            <div style="font-size: 0.85rem; color: #8b949e;">
                Target Faculty: <strong>{selected_prof.name}</strong> ({selected_prof.institution or 'N/A'}) | 
                Paper Year: <strong>{selected_paper.year or 'N/A'}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Core Content Tabs / Cards
    b_col1, b_col2 = st.columns([1, 1])

    with b_col1:
        st.markdown("### 🔬 Paper Analysis")
        st.markdown(
            f"""
            <div class="artemis-card">
                <div class="artemis-card-header">Core Research Problem</div>
                <p style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.5;">
                    {active_brief.research_problem}
                </p>
                <div class="artemis-card-header" style="margin-top: 14px;">Methodology & Approach</div>
                <p style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.5;">
                    {active_brief.methodology}
                </p>
                <div class="artemis-card-header" style="margin-top: 14px;">Main Contribution</div>
                <p style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.5;">
                    {active_brief.key_contribution}
                </p>
                <div class="artemis-card-header" style="margin-top: 14px;">Textual Boundaries & Limitations</div>
                <p style="color: #e3b341; font-size: 0.88rem; line-height: 1.5;">
                    {active_brief.limitations}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b_col2:
        st.markdown("### 🎯 Résumé Alignment & Evidence")
        
        # Matched Evidence Items
        matched_items = [e for e in evidence_items if e.id in active_brief.matched_evidence_ids]
        matched_html = ""
        if matched_items:
            for item in matched_items:
                skills_tag = f"<span class='artemis-badge badge-neutral'>Skills: {', '.join(item.skills[:3])}</span>" if item.skills else ""
                matched_html += f"""
                <div style="background: #0d1117; border-left: 3px solid #3fb950; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px;">
                    <div style="font-weight: 600; color: #f0f6fc; font-size: 0.88rem;">{item.title} ({item.category})</div>
                    <div style="font-size: 0.82rem; color: #8b949e; margin: 2px 0;">{item.description}</div>
                    <div>{skills_tag}</div>
                </div>
                """
        else:
            matched_html = "<p style='color: #8b949e; font-size: 0.88rem;'>No specific student evidence claims linked.</p>"

        st.markdown(
            f"""
            <div class="artemis-card">
                <div class="artemis-card-header">Matched Student Evidence ({len(matched_items)})</div>
                {matched_html}
                <div class="artemis-card-header" style="margin-top: 14px;">Concrete Evidence Connections</div>
                <p style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.5;">
                    {active_brief.relevant_skills_and_projects}
                </p>
                <div class="artemis-card-header" style="margin-top: 14px;">Identified Skill / Knowledge Gaps</div>
                <p style="color: #f85149; font-size: 0.88rem; line-height: 1.5;">
                    {active_brief.potential_gaps}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Suggested Questions Card
    st.markdown("### 💬 Suggested Discussion Questions for Professor")
    if active_brief.suggested_questions:
        q_html = "".join([
            f"<li style='margin-bottom: 8px; color: #c9d1d9;'>{q}</li>"
            for q in active_brief.suggested_questions
        ])
        st.markdown(
            f"""
            <div class="artemis-card">
                <ul style="padding-left: 20px; margin: 0;">
                    {q_html}
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("No suggested questions generated.")

    # Action to Generate Outreach Draft
    st.markdown("---")
    c_draft_btn, c_draft_info = st.columns([2, 3])
    with c_draft_btn:
        if st.button("✉️ Generate Outreach Draft from this Brief", type="primary", use_container_width=True):
            with st.spinner("Drafting review-only outreach email..."):
                try:
                    generator = DraftGenerator(llm_provider=get_active_llm_provider())
                    draft = generator.generate_draft(
                        professor=selected_prof,
                        brief=active_brief,
                        paper=selected_paper,
                        evidence=evidence_items,
                        student_name="Student Researcher",
                    )
                    repo.create_draft(draft)
                    st.session_state["selected_draft_id"] = draft.id
                    st.session_state["current_view"] = "Outreach Draft Review"
                    st.success("Draft created! Navigating to Outreach Draft Review...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate draft: {e}")
    with c_draft_info:
        st.caption("Drafts are strictly saved as **Pending Review** in local SQLite. A.R.T.E.M.I.S. never automatically transmits emails.")
