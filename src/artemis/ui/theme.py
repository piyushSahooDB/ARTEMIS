"""Custom CSS and theme styling for the A.R.T.E.M.I.S. Research Intelligence Dashboard."""

import streamlit as st


def apply_custom_css() -> None:
    """Inject custom dark navy / charcoal & muted gold CSS styles into Streamlit."""
    st.markdown(
        """
        <style>
        /* General page layout and typography */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1280px;
        }

        /* Metric cards */
        .artemis-metric-card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px 20px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        .artemis-metric-val {
            font-size: 2.2rem;
            font-weight: 700;
            color: #e6af2e;
            margin: 4px 0;
            line-height: 1.1;
        }
        .artemis-metric-label {
            font-size: 0.85rem;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }

        /* Container cards */
        .artemis-card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 18px 22px;
            margin-bottom: 16px;
        }
        .artemis-card-header {
            font-size: 1.1rem;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 8px;
            border-bottom: 1px solid #21262d;
            padding-bottom: 6px;
        }

        /* Badges */
        .artemis-badge {
            display: inline-block;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 12px;
            line-height: 1.4;
            margin-right: 6px;
            margin-bottom: 4px;
        }
        .badge-verified {
            background-color: #0d2818;
            color: #3fb950;
            border: 1px solid #238636;
        }
        .badge-unverified {
            background-color: #2e1f00;
            color: #e3b341;
            border: 1px solid #9e6a03;
        }
        .badge-abstract {
            background-color: #0c2135;
            color: #58a6ff;
            border: 1px solid #1f6feb;
        }
        .badge-gold {
            background-color: #2b2203;
            color: #e6af2e;
            border: 1px solid #d29922;
        }
        .badge-danger {
            background-color: #2b0c10;
            color: #f85149;
            border: 1px solid #da3633;
        }
        .badge-neutral {
            background-color: #21262d;
            color: #8b949e;
            border: 1px solid #30363d;
        }

        /* Quality Control Box */
        .quality-card {
            background-color: #161b22;
            border-left: 4px solid #e6af2e;
            border-top: 1px solid #30363d;
            border-right: 1px solid #30363d;
            border-bottom: 1px solid #30363d;
            border-radius: 4px;
            padding: 14px 18px;
            margin-top: 12px;
            margin-bottom: 16px;
        }

        /* Disclaimer Pill */
        .disclaimer-pill {
            background-color: #21262d;
            border: 1px solid #e6af2e;
            color: #e6af2e;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 0.85rem;
            margin-bottom: 16px;
        }

        /* Sidebar branding */
        .sidebar-brand {
            font-size: 1.4rem;
            font-weight: 800;
            color: #e6af2e;
            letter-spacing: 0.05em;
            margin-bottom: 2px;
        }
        .sidebar-subbrand {
            font-size: 0.75rem;
            color: #8b949e;
            line-height: 1.2;
            margin-bottom: 20px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
