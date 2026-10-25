"""Section F: Outreach Draft Review interface with live quality control and editing."""

import streamlit as st

from artemis.ui.components.quality import analyze_email_draft
from artemis.ui.state import get_repository


def render_drafts() -> None:
    """Render the Outreach Draft Review workspace with live quality control and SQLite persistence."""
    repo = get_repository()

    st.markdown("## ✉️ Outreach Draft Review")
    st.markdown(
        "<p style='color: #8b949e; margin-top: -10px; margin-bottom: 24px;'>"
        "Review, edit, and quality-audit personalized cold outreach emails before manual sending."
        "</p>",
        unsafe_allow_html=True,
    )

    # Mandatory Safety Banner
    st.markdown(
        """
        <div class="disclaimer-pill">
            🛡️ <strong>Safety Guarantee:</strong> A.R.T.E.M.I.S. creates review drafts only and <strong>never sends emails automatically</strong>. 
            All outreach drafts require your manual review, verification, and personal transmission.
        </div>
        """,
        unsafe_allow_html=True,
    )

    drafts = repo.list_drafts()
    if not drafts:
        st.info("No email drafts in database yet. Generate a draft from the **Research Brief Workspace** first.")
        return

    # Filter & Draft Selector
    col_filter, col_select = st.columns([2, 4])
    with col_filter:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Pending Review Only", "Approved / Reviewed Only"],
        )

    filtered_drafts = drafts
    if status_filter == "Pending Review Only":
        filtered_drafts = [d for d in drafts if getattr(d, "status", "") == "draft_pending"]
    elif status_filter == "Approved / Reviewed Only":
        filtered_drafts = [d for d in drafts if getattr(d, "status", "") != "draft_pending"]

    if not filtered_drafts:
        st.warning(f"No drafts match the filter '{status_filter}'.")
        return

    preselected_draft_id = st.session_state.get("selected_draft_id")
    draft_index = 0
    if preselected_draft_id:
        for idx, d in enumerate(filtered_drafts):
            if d.id == preselected_draft_id:
                draft_index = idx
                break

    with col_select:
        selected_draft = st.selectbox(
            "Select Draft to Inspect",
            options=filtered_drafts,
            index=draft_index,
            format_func=lambda d: f"{d.recipient_name} — {d.subject[:45]}... ({d.status})",
        )

    # Retrieve associated records
    prof = repo.get_professor(selected_draft.professor_id) if selected_draft.professor_id else None
    paper = repo.get_paper(selected_draft.paper_id) if selected_draft.paper_id else None

    # Header Card with Recipient Context
    email_ver = getattr(prof, "email_verification_status", "unverified") if prof else "unverified"
    if selected_draft.recipient_email:
        if email_ver == "verified":
            recip_badge = f"<span class='artemis-badge badge-verified'>✓ Verified Email: {selected_draft.recipient_email}</span>"
        else:
            recip_badge = f"<span class='artemis-badge badge-unverified'>⚠ Scraped / Unverified: {selected_draft.recipient_email}</span>"
    else:
        recip_badge = "<span class='artemis-badge badge-danger'>No Recipient Email</span>"

    status_badge = (
        "<span class='artemis-badge badge-gold'>PENDING REVIEW</span>"
        if selected_draft.status == "draft_pending"
        else "<span class='artemis-badge badge-verified'>REVIEWED / READY</span>"
    )

    prof_inst = prof.institution if prof and prof.institution else "Unknown Institution"
    paper_title = paper.title if paper else "Academic Research"

    st.markdown(
        f"""
        <div class="artemis-card" style="margin-top: 10px;">
            <div style="margin-bottom: 6px;">
                {status_badge}
                {recip_badge}
            </div>
            <div style="font-size: 1.15rem; font-weight: 700; color: #f0f6fc;">
                To: {selected_draft.recipient_name} <span style="font-size: 0.85rem; font-weight: 400; color: #8b949e;">({prof_inst})</span>
            </div>
            <div style="font-size: 0.85rem; color: #8b949e; margin-top: 4px;">
                Referencing Paper: <span style="color: #58a6ff;">{paper_title}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Editable Draft Area
    st.markdown("### ✍️ Draft Editor")

    edited_subject = st.text_input(
        "Subject Line",
        value=selected_draft.subject,
        key=f"subj_{selected_draft.id}",
    )

    edited_body = st.text_area(
        "Email Body",
        value=selected_draft.body,
        height=280,
        key=f"body_{selected_draft.id}",
        help="Edit the body directly. Live Quality Control will update automatically.",
    )

    # Live Quality Control Card
    quality_report = analyze_email_draft(
        body=edited_body,
        subject=edited_subject,
        recipient_email=selected_draft.recipient_email,
        paper_title=paper_title,
        email_verification_status=email_ver,
    )

    wc_color = "#3fb950" if quality_report.is_word_count_ok else "#e3b341"
    hallucination_html = ""
    if quality_report.hallucination_warnings:
        for w in quality_report.hallucination_warnings:
            hallucination_html += f"<li style='color: #f85149; font-size: 0.85rem;'>{w}</li>"
    else:
        hallucination_html = "<li style='color: #3fb950; font-size: 0.85rem;'>✓ No prohibited or assumed familiarity phrases detected.</li>"

    recipient_html = ""
    if quality_report.recipient_warnings:
        for w in quality_report.recipient_warnings:
            recipient_html += f"<li style='color: #e3b341; font-size: 0.85rem;'>{w}</li>"
    else:
        recipient_html = "<li style='color: #3fb950; font-size: 0.85rem;'>✓ Official recipient contact verified.</li>"

    grounding_html = ""
    if quality_report.grounding_warnings:
        for w in quality_report.grounding_warnings:
            grounding_html += f"<li style='color: #e3b341; font-size: 0.85rem;'>{w}</li>"
    else:
        grounding_html = "<li style='color: #3fb950; font-size: 0.85rem;'>✓ Referenced target paper matches research context.</li>"

    st.markdown(
        f"""
        <div class="quality-card">
            <div style="font-weight: 700; color: #f0f6fc; font-size: 1rem; margin-bottom: 8px;">
                🔍 Automated Quality Control & Fact Verification
            </div>
            <div style="margin-bottom: 8px;">
                <span style="font-weight: 600; color: {wc_color}; font-size: 0.88rem;">
                    • Length Check: {quality_report.word_count_feedback}
                </span>
            </div>
            <div style="font-size: 0.88rem; font-weight: 600; color: #c9d1d9; margin-top: 6px;">
                Anti-Hallucination & Evidence Grounding:
            </div>
            <ul style="padding-left: 20px; margin: 4px 0 8px 0;">
                {hallucination_html}
                {recipient_html}
                {grounding_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action Buttons
    c_save, c_status, c_copy = st.columns([2, 2, 2])

    with c_save:
        if st.button("💾 Save Edits to Database", use_container_width=True, type="primary"):
            selected_draft.subject = edited_subject
            selected_draft.body = edited_body
            repo.update_draft(selected_draft)
            st.success("Draft updated successfully in SQLite database!")

    with c_status:
        if selected_draft.status == "draft_pending":
            if st.button("✅ Mark as Reviewed", use_container_width=True):
                selected_draft.status = "reviewed"
                selected_draft.subject = edited_subject
                selected_draft.body = edited_body
                repo.update_draft(selected_draft)
                st.success("Draft marked as Reviewed!")
                st.rerun()
        else:
            if st.button("↩️ Revert to Pending", use_container_width=True):
                selected_draft.status = "draft_pending"
                repo.update_draft(selected_draft)
                st.info("Status set back to Pending Review.")
                st.rerun()

    with c_copy:
        # Display copyable text expander
        with st.expander("📋 Copy Formatted Text", expanded=False):
            st.text_area(
                "Plaintext for Clipboard",
                value=f"Subject: {edited_subject}\n\n{edited_body}",
                height=150,
            )
