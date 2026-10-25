"""A.R.T.E.M.I.S. — Research Intelligence Dashboard.

Autonomous Research Tracking, Exploration, Matching & Intelligent Scouting.
Local-first, review-only research outreach assistant.
"""

import streamlit as st

from artemis.ui.state import init_session_state
from artemis.ui.theme import apply_custom_css
from artemis.ui.views.briefs import render_briefs
from artemis.ui.views.dashboard import render_dashboard
from artemis.ui.views.drafts import render_drafts
from artemis.ui.views.papers import render_papers
from artemis.ui.views.professors import render_professors
from artemis.ui.views.scout import render_scout
from artemis.ui.views.settings import render_settings


def main() -> None:
    # 1. Page Configuration
    st.set_page_config(
        page_title="A.R.T.E.M.I.S. Research Dashboard",
        page_icon="🏹",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 2. Inject CSS Theme
    apply_custom_css()

    # 3. Initialize Session State
    init_session_state()

    # 4. Sidebar Branding & Navigation
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">🏹 A.R.T.E.M.I.S.</div>
            <div class="sidebar-subbrand">
                Autonomous Research Tracking, Exploration, Matching & Intelligent Scouting
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav_options = [
            "Dashboard",
            "Research Scout",
            "Professor Explorer",
            "Paper Explorer",
            "Research Brief Workspace",
            "Outreach Draft Review",
            "Settings & Status",
        ]

        # Sync navigation with session state
        current_view = st.session_state.get("current_view", "Dashboard")
        nav_index = nav_options.index(current_view) if current_view in nav_options else 0

        selected_view = st.radio(
            "Navigation",
            options=nav_options,
            index=nav_index,
            label_visibility="collapsed",
        )

        st.session_state["current_view"] = selected_view

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size: 0.78rem; color: #8b949e; line-height: 1.4;">
                <strong style="color: #e6af2e;">🛡️ Review-Only Assistant:</strong><br>
                Grounded in verifiable facts.<br>
                Never sends emails automatically.<br>
                Local SQLite persistence.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 5. Route to Selected View
    if selected_view == "Dashboard":
        render_dashboard()
    elif selected_view == "Research Scout":
        render_scout()
    elif selected_view == "Professor Explorer":
        render_professors()
    elif selected_view == "Paper Explorer":
        render_papers()
    elif selected_view == "Research Brief Workspace":
        render_briefs()
    elif selected_view == "Outreach Draft Review":
        render_drafts()
    elif selected_view == "Settings & Status":
        render_settings()


if __name__ == "__main__":
    main()
