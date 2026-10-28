"""Professional styling and component styling for Internal Company Knowledge Assistant.

Provides clean, accessible CSS with modern typography, subtle borders, and
clear visual hierarchy appropriate for an academic enterprise software project.
"""

from __future__ import annotations

import streamlit as st


def apply_custom_styles() -> None:
    """Inject custom CSS for consistent, elegant UI presentation."""
    st.markdown(
        """
        <style>
        /* Base typography and layout refinement */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Top header container */
        .app-header {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            color: #FFFFFF;
            padding: 1.5rem 2rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .app-header h1 {
            color: #FFFFFF !important;
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
            letter-spacing: -0.025em;
        }
        .app-header p {
            color: #94A3B8;
            font-size: 0.95rem;
            margin: 0.35rem 0 0 0;
        }

        /* Stat cards */
        .metric-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .metric-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        }
        .metric-label {
            font-size: 0.825rem;
            text-transform: uppercase;
            font-weight: 600;
            color: #64748B;
            letter-spacing: 0.05em;
        }
        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #0F172A;
            margin-top: 0.25rem;
        }

        /* Status Badges */
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-align: center;
        }
        .badge-approved { background-color: #DEF7EC; color: #03543F; }
        .badge-pending { background-color: #FEF08A; color: #713F12; }
        .badge-rejected { background-color: #FDE8E8; color: #9B1C1C; }
        .badge-revoked { background-color: #F3F4F6; color: #374151; }
        .badge-public { background-color: #E1EFFE; color: #1E429F; }
        .badge-restricted { background-color: #FCE8E6; color: #9C1A1A; }
        .badge-confidential { background-color: #EDEBFE; color: #5521B5; }

        /* Citation Card */
        .citation-box {
            background-color: #F8FAFC;
            border-left: 4px solid #0284C7;
            border-top: 1px solid #E2E8F0;
            border-right: 1px solid #E2E8F0;
            border-bottom: 1px solid #E2E8F0;
            border-radius: 0 8px 8px 0;
            padding: 0.85rem 1.15rem;
            margin-bottom: 0.75rem;
        }
        .citation-title {
            font-weight: 600;
            font-size: 0.95rem;
            color: #0369A1;
        }
        .citation-meta {
            font-size: 0.8rem;
            color: #64748B;
            margin-top: 0.2rem;
        }
        .citation-excerpt {
            font-size: 0.875rem;
            color: #334155;
            font-style: italic;
            margin-top: 0.4rem;
            padding-left: 0.5rem;
            border-left: 2px solid #CBD5E1;
        }

        /* Answer banner */
        .answer-banner {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1.25rem;
        }

        /* Disclaimer footer note */
        .system-disclaimer {
            font-size: 0.8rem;
            color: #94A3B8;
            border-top: 1px solid #E2E8F0;
            padding-top: 1rem;
            margin-top: 2rem;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str) -> None:
    """Render a standard clean application banner."""
    st.markdown(
        f"""
        <div class="app-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_status_badge(status: str) -> str:
    """Return an HTML badge for document status."""
    class_map = {
        "Approved": "badge badge-approved",
        "Pending Approval": "badge badge-pending",
        "Rejected": "badge badge-rejected",
        "Revoked": "badge badge-revoked",
    }
    css_class = class_map.get(status, "badge badge-pending")
    return f'<span class="{css_class}">{status}</span>'


def format_classification_badge(classification: str) -> str:
    """Return an HTML badge for document classification."""
    class_map = {
        "Public": "badge badge-public",
        "Restricted": "badge badge-restricted",
        "Confidential": "badge badge-confidential",
    }
    css_class = class_map.get(classification, "badge badge-public")
    return f'<span class="{css_class}">{classification}</span>'
