"""Main Streamlit Application for Internal Company Knowledge Assistant.

Provides an intuitive, role-aware interface for employees and administrators to search,
upload, review, and cite approved company documentation with local SQLite persistence
and TF-IDF similarity ranking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from backend.access_control import (
    can_manage_users,
    can_review_documents,
    can_upload_documents,
    can_user_access_document,
    is_admin,
)
from backend.authentication import (
    assign_user_groups,
    authenticate_user,
    create_user,
    get_user_by_id,
    initialize_admin_if_empty,
    list_users,
    update_user_role,
    update_user_status,
)
from backend.database import (
    DEFAULT_DB_PATH,
    get_db_connection,
    init_db,
    seed_initial_data,
)
from backend.knowledge_service import KnowledgeService
from backend.retriever import get_retriever
from frontend.styles import (
    apply_custom_styles,
    format_classification_badge,
    format_status_badge,
    render_header,
)

# Page configuration
st.set_page_config(
    page_title="Internal Company Knowledge Assistant",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_service() -> KnowledgeService:
    """Initialize database, default admin, seed data, and return KnowledgeService singleton."""
    init_db()
    seed_initial_data()
    admin_id = initialize_admin_if_empty(default_password="Admin@12345")
    service = KnowledgeService()

    # Auto-seed sample documents if database has 0 documents
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents;")
        doc_count = cursor.fetchone()[0]

    if doc_count == 0:
        sample_dir = Path(__file__).resolve().parent / "data" / "sample_documents"
        admin_rec = get_user_by_id(admin_id) or {
            "user_id": admin_id,
            "username": "admin",
            "role": "Administrator",
            "status": "Active",
            "group_ids": ["grp_general", "grp_hr", "grp_eng", "grp_finance", "grp_exec"],
        }
        if sample_dir.exists():
            # Seed FAQ
            p_faq = sample_dir / "FAQ_Remote_Work_and_Leave.txt"
            if p_faq.exists():
                with open(p_faq, "rb") as f:
                    service.upload_and_process_document(
                        filename="FAQ_Remote_Work_and_Leave.txt",
                        content_bytes=f.read(),
                        title="Remote Work & Leave Policy FAQ",
                        category="cat_faq",
                        classification="Public",
                        user=admin_rec,
                        auto_approve_if_admin=True,
                    )

            # Seed Pricing DOCX
            p_pricing = sample_dir / "Service_Cloud_Hosting_Pricing_Rules.docx"
            if p_pricing.exists():
                with open(p_pricing, "rb") as f:
                    service.upload_and_process_document(
                        filename="Service_Cloud_Hosting_Pricing_Rules.docx",
                        content_bytes=f.read(),
                        title="Cloud Hosting Pricing Rules & SLAs",
                        category="cat_pricing",
                        classification="Public",
                        user=admin_rec,
                        auto_approve_if_admin=True,
                    )

            # Seed SOP PDF
            p_sop = sample_dir / "SOP_IT_Incident_Management.pdf"
            if p_sop.exists():
                with open(p_sop, "rb") as f:
                    service.upload_and_process_document(
                        filename="SOP_IT_Incident_Management.pdf",
                        content_bytes=f.read(),
                        title="IT Incident Management SOP",
                        category="cat_sop",
                        classification="Public",
                        user=admin_rec,
                        auto_approve_if_admin=True,
                    )

            # Seed Confidential Executive Notes
            p_conf = sample_dir / "CONFIDENTIAL_Executive_Compensation_2026.txt"
            if p_conf.exists():
                with open(p_conf, "rb") as f:
                    service.upload_and_process_document(
                        filename="CONFIDENTIAL_Executive_Compensation_2026.txt",
                        content_bytes=f.read(),
                        title="Executive Leadership Strategy & Bonus Pool",
                        category="cat_policy",
                        classification="Confidential",
                        target_group_ids=["grp_exec"],
                        user=admin_rec,
                        auto_approve_if_admin=True,
                    )

    # Build or ensure retriever index
    retriever = get_retriever()
    retriever.build_index()
    return service


def init_session() -> None:
    """Initialize required session state keys."""
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "current_question" not in st.session_state:
        st.session_state["current_question"] = ""
    if "last_answer" not in st.session_state:
        st.session_state["last_answer"] = None


def render_login_screen(service: KnowledgeService) -> None:
    """Render the user login and demonstration quick-access interface."""
    render_header(
        "Internal Company Knowledge Assistant",
        "Sign in to search, review, and manage approved company documentation.",
    )

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("Account Sign In")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="e.g. admin or employee username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", use_container_width=True)

            if submit:
                if not username or not password:
                    st.error("Please enter both username and password.")
                else:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state["user"] = user
                        st.success(f"Welcome back, {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password, or account is disabled.")

    with col2:
        st.subheader("Academic Demonstration Quick-Login")
        st.info(
            "For academic presentation and evaluation, click a preconfigured role below to log in instantly:"
        )

        if st.button("🔑 Sign in as Administrator (admin)", use_container_width=True):
            user = authenticate_user("admin", "Admin@12345")
            if user:
                st.session_state["user"] = user
                st.rerun()

        # Check if a sample employee exists; if not, create one
        emp_check = authenticate_user("employee_demo", "Emp@12345")
        if not emp_check:
            try:
                create_user(
                    username="employee_demo",
                    password="Emp@12345",
                    full_name="Alex Taylor (Standard Employee)",
                    role="Employee",
                    group_ids=["grp_general", "grp_eng"],
                )
            except Exception:
                pass

        if st.button("👤 Sign in as Standard Employee (employee_demo)", use_container_width=True):
            user = authenticate_user("employee_demo", "Emp@12345")
            if user:
                st.session_state["user"] = user
                st.rerun()

        st.caption("Default Admin Credentials: `username: admin` | `password: Admin@12345`")


def render_sidebar(service: KnowledgeService) -> str:
    """Render the user profile, role badge, and navigation menu."""
    user = st.session_state["user"]
    st.sidebar.markdown(f"### 🏢 Knowledge Assistant")
    st.sidebar.markdown(f"**{user['full_name']}**")
    role_color = "#0284C7" if user["role"] == "Administrator" else "#10B981"
    st.sidebar.markdown(
        f'<span style="background-color: {role_color}22; color: {role_color}; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">Role: {user["role"]}</span>',
        unsafe_allow_html=True,
    )

    if user.get("groups"):
        group_names = ", ".join(g["group_name"] for g in user["groups"] if g["group_name"] != "All Employees")
        if group_names:
            st.sidebar.caption(f"Groups: {group_names}")

    st.sidebar.markdown("---")

    nav_options = [
        "🏠 Dashboard",
        "🔍 Ask Knowledge Assistant",
        "📚 Document Library",
        "📤 Upload Documents",
    ]

    if can_review_documents(user):
        nav_options.append("⚖️ Document Review")

    if can_manage_users(user):
        nav_options.append("👥 User Management")

    nav_options.append("📜 My Question History")

    if is_admin(user):
        nav_options.append("⚙️ System Settings")

    choice = st.sidebar.radio("Navigation", nav_options, index=1)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        st.session_state["user"] = None
        st.session_state["last_answer"] = None
        st.session_state["current_question"] = ""
        st.rerun()

    return choice


# -----------------------------------------------------------------------------
# PAGE: Dashboard
# -----------------------------------------------------------------------------
def page_dashboard(service: KnowledgeService) -> None:
    render_header("Assistant Overview & Analytics", "Summary of approved internal company documents and system metrics.")
    user = st.session_state["user"]

    # Gather metrics
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'Approved';")
        approved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'Pending Approval';")
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM document_chunks;")
        total_chunks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Approved Documents</div><div class="metric-value">{approved_count}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Pending Approval</div><div class="metric-value">{pending_count}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Indexed Text Chunks</div><div class="metric-value">{total_chunks}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Registered Accounts</div><div class="metric-value">{user_count}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Document categories summary
    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.subheader("Document Categories Distribution")
        with get_db_connection() as conn:
            df_cat = pd.read_sql_query(
                """
                SELECT c.category_name as "Category", COUNT(d.document_id) as "Documents"
                FROM document_categories c
                LEFT JOIN documents d ON c.category_id = d.category AND d.status = 'Approved'
                GROUP BY c.category_name
                ORDER BY "Documents" DESC;
                """,
                conn,
            )
        st.bar_chart(df_cat.set_index("Category"))

    with col_right:
        st.subheader("Recent Approved Documents")
        recent_docs = service.list_documents(user, status_filter="Approved")[:5]
        if recent_docs:
            for doc in recent_docs:
                st.markdown(
                    f"**{doc['title']}**  \n"
                    f"<small>{doc['category']} • {doc['file_type'].upper()} • {doc['chunk_count']} chunks</small>",
                    unsafe_allow_html=True,
                )
                st.divider()
        else:
            st.info("No approved documents available yet.")


# -----------------------------------------------------------------------------
# PAGE: Ask Knowledge Assistant
# -----------------------------------------------------------------------------
def page_ask_assistant(service: KnowledgeService) -> None:
    render_header(
        "Ask Company Knowledge Assistant",
        "Natural language Q&A strictly grounded in approved SOPs, FAQs, pricing rules, and policies.",
    )
    user = st.session_state["user"]

    with st.expander("⚙️ Retrieval & Threshold Configuration", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            top_k = st.slider("Max Evidence Chunks (Top-K)", min_value=1, max_value=8, value=5)
        with c2:
            min_score = st.slider(
                "Minimum Relevance Cutoff (Cosine Similarity)",
                min_value=0.05,
                max_value=0.40,
                value=0.12,
                step=0.01,
            )
        st.caption("Only approved documents authorized for your user account and group memberships will be searched.")

    # Search form
    with st.form("ask_form"):
        query = st.text_input(
            "Enter your question in natural language:",
            placeholder="e.g. What are the core collaboration hours? or What discount applies to a 12-month contract?",
            value=st.session_state["current_question"],
        )
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            submitted = st.form_submit_button("🔍 Search Knowledge", use_container_width=True)
        with col_btn2:
            clear_btn = st.form_submit_button("Clear", use_container_width=False)

    if clear_btn:
        st.session_state["current_question"] = ""
        st.session_state["last_answer"] = None
        st.rerun()

    if submitted:
        if not query.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Searching approved authorized documents and synthesizing citations..."):
                answer = service.ask_question(
                    query=query,
                    user=user,
                    top_k=top_k,
                    min_score=min_score,
                    log_history=True,
                )
                st.session_state["last_answer"] = answer
                st.session_state["current_question"] = query

    # Render answer if available
    ans = st.session_state["last_answer"]
    if ans:
        st.markdown("<br>", unsafe_allow_html=True)
        if ans.status == "answered":
            st.success("✅ Grounded Answer Established from Approved Documents")
            st.markdown(f'<div class="answer-banner">{ans.answer_text}</div>', unsafe_allow_html=True)

            # Display Citations
            st.subheader(f"Verifiable Source Citations ({len(ans.citations)})")
            for cit in ans.citations:
                page_info = f" • Page {cit.page_number}" if cit.page_number is not None else ""
                section_info = f" • Section: {cit.section_heading}" if cit.section_heading else ""
                st.markdown(
                    f"""
                    <div class="citation-box">
                        <div class="citation-title">📄 {cit.document_title}</div>
                        <div class="citation-meta">Category: {cit.document_category}{page_info}{section_info} • Relevance Score: {cit.similarity_score:.3f}</div>
                        <div class="citation-excerpt">"{cit.supporting_excerpt}"</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Option to preview full chunk if authorized
                with st.expander(f"Preview Source Content for: {cit.document_title}"):
                    st.write(cit.supporting_excerpt)
                    st.caption(f"Document ID: {cit.document_id} • Classification: {cit.classification}")

        elif ans.status == "insufficient_evidence":
            st.warning("⚠️ Insufficient Evidence Found")
            st.markdown(
                f'<div class="answer-banner" style="border-left: 4px solid #F59E0B;">{ans.answer_text}</div>',
                unsafe_allow_html=True,
            )
            st.info(
                "💡 **Suggestions:**  \n"
                "- Check for typos or rephrase your search terms.  \n"
                "- The requested topic may be documented in an unapproved or restricted document.  \n"
                "- Contact your department lead or an Administrator if you believe this document should be uploaded."
            )


# -----------------------------------------------------------------------------
# PAGE: Document Library
# -----------------------------------------------------------------------------
def page_document_library(service: KnowledgeService) -> None:
    render_header("Approved Document Library", "Browse, search, and preview company documents authorized for your account.")
    user = st.session_state["user"]

    categories = service.get_categories()
    cat_options = ["All Categories"] + [c["category_name"] for c in categories]
    cat_id_map = {c["category_name"]: c["category_id"] for c in categories}

    col1, col2 = st.columns(2)
    with col1:
        selected_cat = st.selectbox("Filter by Category", cat_options)
    with col2:
        selected_class = st.selectbox("Filter by Classification", ["All Classifications", "Public", "Restricted", "Confidential"])

    cat_filter = cat_id_map.get(selected_cat) if selected_cat != "All Categories" else None
    docs = service.list_documents(user, status_filter="Approved", category_filter=cat_filter)

    if selected_class != "All Classifications":
        docs = [d for d in docs if d["classification"] == selected_class]

    st.markdown(f"**Showing {len(docs)} approved document(s):**")

    if not docs:
        st.info("No approved documents matching your filters were found.")
        return

    for doc in docs:
        with st.container():
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: #0F172A;">{doc['title']}</h4>
                        <div>
                            {format_status_badge(doc['status'])}
                            {format_classification_badge(doc['classification'])}
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: #64748B; margin-top: 0.35rem;">
                        Format: <b>{doc['file_type'].upper()}</b> • Size: {doc['file_size']} bytes • 
                        Chunks: <b>{doc['chunk_count']}</b> • Uploaded: {doc['uploaded_at'][:10]} by {doc['uploader_name'] or 'System'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Preview chunks expander
            with st.expander(f"📖 Preview text chunks for: {doc['title']}"):
                try:
                    chunks = service.get_document_chunks_for_preview(doc["document_id"], user)
                    for c in chunks:
                        heading = f" - {c['section_heading']}" if c["section_heading"] else ""
                        page = f" (Page {c['page_number']})" if c["page_number"] else ""
                        st.markdown(f"**Chunk #{c['chunk_index'] + 1}{heading}{page}** ({c['word_count']} words):")
                        st.text(c["chunk_text"])
                        st.divider()
                except PermissionError as e:
                    st.error(str(e))


# -----------------------------------------------------------------------------
# PAGE: Upload Documents
# -----------------------------------------------------------------------------
def page_upload_documents(service: KnowledgeService) -> None:
    render_header(
        "Upload Company Documents",
        "Submit PDF, DOCX, or TXT documentation for cryptographic integrity validation and approval.",
    )
    user = st.session_state["user"]

    if not can_upload_documents(user):
        st.error("You are not authorized to upload documents.")
        return

    categories = service.get_categories()
    cat_names = [c["category_name"] for c in categories]
    cat_map = {c["category_name"]: c["category_id"] for c in categories}
    access_groups = service.get_access_groups()

    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader(
            "Choose a document file (PDF, DOCX, TXT):",
            type=["pdf", "docx", "txt"],
            help="Maximum permitted file size is 25 MB. Text extraction preserves page numbers for PDFs and headings for DOCX.",
        )

        title = st.text_input("Document Display Title", placeholder="e.g. Employee Travel Reimbursement SOP 2026")
        selected_cat_name = st.selectbox("Category", cat_names)
        classification = st.selectbox(
            "Access Classification",
            ["Public", "Restricted", "Confidential"],
            help="Public: Available to all employees. Restricted/Confidential: Available only to selected groups or Administrators.",
        )

        target_groups = []
        if classification in ("Restricted", "Confidential"):
            group_options = {g["group_name"]: g["group_id"] for g in access_groups}
            selected_grp_names = st.multiselect(
                "Authorized Access Groups (who can read this document):",
                list(group_options.keys()),
                default=[g["group_name"] for g in access_groups if g["group_id"] in user.get("group_ids", [])],
            )
            target_groups = [group_options[name] for name in selected_grp_names]

        auto_approve = False
        if is_admin(user):
            auto_approve = st.checkbox("⚡ Auto-Approve immediately (Administrator Bypass)", value=True)

        submitted = st.form_submit_button("Upload and Process Document", use_container_width=True)

        if submitted:
            if not uploaded_file:
                st.error("Please select a file to upload.")
            elif not title.strip():
                st.error("Please enter a document title.")
            else:
                content_bytes = uploaded_file.read()
                category_id = cat_map[selected_cat_name]

                with st.spinner("Extracting text, computing SHA-256 hash, and building chunks..."):
                    result = service.upload_and_process_document(
                        filename=uploaded_file.name,
                        content_bytes=content_bytes,
                        title=title.strip(),
                        category=category_id,
                        classification=classification,
                        user=user,
                        target_group_ids=target_groups,
                        auto_approve_if_admin=auto_approve,
                    )

                if result["success"]:
                    st.success(
                        f"✅ Document successfully uploaded! Status: **{result['status']}**  \n"
                        f"- Total words extracted: **{result['total_words']}**  \n"
                        f"- Chunks created: **{result['total_chunks']}**  \n"
                        f"- Pages or sections: **{result['pages_or_sections']}**"
                    )
                    if result["status"] == "Pending Approval":
                        st.info("Your document has been submitted and is awaiting administrative review before it appears in search.")
                else:
                    st.error(f"❌ Upload rejected: {result.get('error')}")


# -----------------------------------------------------------------------------
# PAGE: Document Review & Approval (Admin / Reviewer)
# -----------------------------------------------------------------------------
def page_document_review(service: KnowledgeService) -> None:
    render_header(
        "Document Review & Approval Workflow",
        "Evaluate newly uploaded documents, verify extracted text, approve for indexing, or reject with cause.",
    )
    user = st.session_state["user"]

    if not can_review_documents(user):
        st.error("Access Denied: Only Administrators or Reviewers may access this review interface.")
        return

    tab_pending, tab_approved = st.tabs(["⏳ Pending Approval", "✅ Approved Documents Management"])

    with tab_pending:
        pending_docs = service.list_documents(user, status_filter="Pending Approval")
        st.markdown(f"**{len(pending_docs)} document(s) currently awaiting review:**")

        if not pending_docs:
            st.success("🎉 All documents have been reviewed. No documents currently pending.")
        else:
            for doc in pending_docs:
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background-color: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;">
                            <div style="display: flex; justify-content: space-between;">
                                <h4 style="margin: 0; color: #92400E;">{doc['title']}</h4>
                                <div>{format_classification_badge(doc['classification'])}</div>
                            </div>
                            <div style="font-size: 0.85rem; color: #78350F; margin-top: 0.35rem;">
                                File: <b>{doc['original_filename']}</b> ({doc['file_type'].upper()}) • 
                                Uploaded by: <b>{doc['uploader_name'] or 'Employee'}</b> on {doc['uploaded_at'][:10]}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    with st.expander(f"Review Extracted Chunks ({doc['chunk_count']} chunks)"):
                        chunks = service.get_document_chunks_for_preview(doc["document_id"], user)
                        for c in chunks:
                            st.caption(f"Chunk #{c['chunk_index'] + 1} - Section: {c['section_heading'] or 'N/A'}")
                            st.text(c["chunk_text"][:300] + ("..." if len(c["chunk_text"]) > 300 else ""))

                    col_app, col_rej = st.columns(2)
                    with col_app:
                        app_notes = st.text_input(f"Approval Notes (optional)", key=f"app_note_{doc['document_id']}")
                        if st.button("✅ Approve & Index Document", key=f"btn_app_{doc['document_id']}", use_container_width=True):
                            service.approve_document(doc["document_id"], user, notes=app_notes)
                            st.success(f"Document '{doc['title']}' approved and indexed!")
                            st.rerun()

                    with col_rej:
                        rej_reason = st.text_input(f"Rejection Reason (required)", key=f"rej_reason_{doc['document_id']}")
                        if st.button("❌ Reject Document", key=f"btn_rej_{doc['document_id']}", use_container_width=True):
                            if not rej_reason.strip():
                                st.error("A clear rejection reason must be specified.")
                            else:
                                service.reject_document(doc["document_id"], user, rejection_reason=rej_reason)
                                st.warning(f"Document '{doc['title']}' rejected.")
                                st.rerun()
                    st.divider()

    with tab_approved:
        approved_docs = service.list_documents(user, status_filter="Approved")
        st.markdown(f"**{len(approved_docs)} approved document(s) currently live in retrieval index:**")

        for doc in approved_docs:
            col_info, col_act = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"**{doc['title']}**  \n"
                    f"<small>{doc['category']} • {doc['file_type'].upper()} • Approved on {doc['reviewed_at'][:10] if doc['reviewed_at'] else 'Initial Setup'}</small>",
                    unsafe_allow_html=True,
                )
            with col_act:
                if st.button("🚫 Revoke Approval", key=f"rev_{doc['document_id']}", use_container_width=True):
                    service.revoke_document_approval(doc["document_id"], user, notes="Manually revoked by reviewer.")
                    st.warning(f"Approval revoked for '{doc['title']}'. Removed from index.")
                    st.rerun()
            st.divider()


# -----------------------------------------------------------------------------
# PAGE: User Management (Admin Only)
# -----------------------------------------------------------------------------
def page_user_management(service: KnowledgeService) -> None:
    render_header("User Accounts & Access Management", "Manage user credentials, assign roles, and configure departmental access groups.")
    admin_user = st.session_state["user"]

    if not is_admin(admin_user):
        st.error("Access Denied: Only Administrators can manage users.")
        return

    tab_users, tab_create = st.tabs(["👥 Registered Accounts", "➕ Register New User"])

    with tab_users:
        users = list_users()
        user_data = []
        for u in users:
            grp_names = ", ".join(g["group_name"] for g in u["groups"])
            user_data.append({
                "User ID": u["user_id"],
                "Username": u["username"],
                "Full Name": u["full_name"],
                "Role": u["role"],
                "Status": u["status"],
                "Assigned Groups": grp_names,
            })
        st.dataframe(pd.DataFrame(user_data), use_container_width=True)

        st.subheader("Edit User Role or Status")
        col1, col2, col3 = st.columns(3)
        with col1:
            target_username = st.selectbox("Select User", [u["username"] for u in users if u["username"] != "admin"])
        with col2:
            target_role = st.selectbox("Role", ["Employee", "Reviewer", "Administrator"])
        with col3:
            target_status = st.selectbox("Status", ["Active", "Disabled"])

        if st.button("Update User Profile"):
            target_u = next(u for u in users if u["username"] == target_username)
            update_user_role(target_u["user_id"], target_role, admin_user["user_id"])
            update_user_status(target_u["user_id"], target_status, admin_user["user_id"])
            st.success(f"Updated user '{target_username}' successfully.")
            st.rerun()

    with tab_create:
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Username (unique)", placeholder="e.g. emily.watson")
            new_fullname = st.text_input("Full Name", placeholder="e.g. Emily Watson")
            new_password = st.text_input("Temporary Password (min 6 characters)", type="password")
            new_role = st.selectbox("Initial Role", ["Employee", "Reviewer", "Administrator"])

            groups = service.get_access_groups()
            group_options = {g["group_name"]: g["group_id"] for g in groups}
            selected_grps = st.multiselect(
                "Assign Access Groups",
                list(group_options.keys()),
                default=["All Employees"],
            )
            selected_grp_ids = [group_options[name] for name in selected_grps]

            submit_create = st.form_submit_button("Register User Account", use_container_width=True)

            if submit_create:
                if not new_username or not new_password or not new_fullname:
                    st.error("Please fill in all required fields.")
                else:
                    try:
                        create_user(
                            username=new_username,
                            password=new_password,
                            full_name=new_fullname,
                            role=new_role,
                            group_ids=selected_grp_ids,
                        )
                        st.success(f"User account '{new_username}' created successfully!")
                    except Exception as e:
                        st.error(f"Failed to create user: {str(e)}")


# -----------------------------------------------------------------------------
# PAGE: Question History
# -----------------------------------------------------------------------------
def page_question_history(service: KnowledgeService) -> None:
    render_header("My Question History", "Review your personal past inquiries, grounded answers, and cited sources.")
    user = st.session_state["user"]

    history = service.get_user_question_history(user["user_id"])

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**Found {len(history)} recorded question(s) for your account:**")
    with col2:
        if history and st.button("🗑️ Clear My History", use_container_width=True):
            deleted = service.clear_user_question_history(user["user_id"])
            st.success(f"Cleared {deleted} history item(s).")
            st.rerun()

    if not history:
        st.info("You haven't asked any questions yet. Use the 'Ask Knowledge Assistant' page to search!")
        return

    for item in history:
        with st.container():
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="font-size: 0.8rem; color: #64748B;">Asked on {item['created_at'][:19].replace('T', ' ')} UTC</div>
                    <h4 style="margin: 0.25rem 0 0.5rem 0; color: #0284C7;">❓ {item['question_text']}</h4>
                    <div style="font-size: 0.9rem; color: #1E293B; white-space: pre-line;">{item['answer_text'][:350]}{'...' if len(item['answer_text']) > 350 else ''}</div>
                    <div style="font-size: 0.8rem; color: #059669; margin-top: 0.5rem; font-weight: 600;">
                        Sources Verified: {item['evidence_count']} excerpt(s)
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# -----------------------------------------------------------------------------
# PAGE: System Settings & Index
# -----------------------------------------------------------------------------
def page_system_settings(service: KnowledgeService) -> None:
    render_header("System Settings & Engine Diagnostics", "Manage retrieval index health, custom categories, and database status.")
    user = st.session_state["user"]

    if not is_admin(user):
        st.error("Access Denied: Only Administrators can view system settings.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("TF-IDF Vector Space Index")
        retriever = get_retriever()
        chunk_count = len(retriever.chunk_metadata)
        vocab_size = len(retriever.vectorizer.vocabulary_) if retriever.is_indexed and retriever.vectorizer.vocabulary_ else 0

        st.write(f"- Indexed Chunks: **{chunk_count}**")
        st.write(f"- Vocabulary Features: **{vocab_size} tokens**")
        st.write(f"- Engine Status: **{'Active & Ready' if retriever.is_indexed else 'Empty'}**")

        if st.button("🔄 Force Rebuild Retrieval Index", use_container_width=True):
            count = retriever.build_index()
            st.success(f"Retriever index rebuilt successfully with {count} chunks!")

    with col2:
        st.subheader("Database & Storage Info")
        db_path = DEFAULT_DB_PATH
        st.write(f"- Database Engine: **SQLite 3 (PRAGMA foreign_keys = ON)**")
        st.write(f"- Database Location: `{db_path.name}`")
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            st.write(f"- Database File Size: **{size_kb:.1f} KB**")

        upload_dir = Path(__file__).resolve().parent / "data" / "uploads"
        if upload_dir.exists():
            upload_files = list(upload_dir.glob("*"))
            st.write(f"- Uploaded Files in Storage: **{len(upload_files)} files**")

    st.divider()

    st.subheader("Add Custom Document Category")
    with st.form("add_cat_form"):
        c_name = st.text_input("Category Name", placeholder="e.g. Compliance Reports")
        c_desc = st.text_input("Category Description", placeholder="e.g. Annual regulatory compliance documentation")
        cat_submit = st.form_submit_button("Create Category")

        if cat_submit:
            if not c_name.strip():
                st.error("Please enter a category name.")
            else:
                try:
                    cat_id = service.add_category(c_name, c_desc, user)
                    st.success(f"Created category '{c_name}' (ID: {cat_id})!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create category: {str(e)}")


# -----------------------------------------------------------------------------
# Main Application Flow
# -----------------------------------------------------------------------------
def main() -> None:
    apply_custom_styles()
    init_session()
    service = get_service()

    if not st.session_state["user"]:
        render_login_screen(service)
    else:
        nav_choice = render_sidebar(service)

        if "Dashboard" in nav_choice:
            page_dashboard(service)
        elif "Ask Knowledge Assistant" in nav_choice:
            page_ask_assistant(service)
        elif "Document Library" in nav_choice:
            page_document_library(service)
        elif "Upload Documents" in nav_choice:
            page_upload_documents(service)
        elif "Document Review" in nav_choice:
            page_document_review(service)
        elif "User Management" in nav_choice:
            page_user_management(service)
        elif "Question History" in nav_choice:
            page_question_history(service)
        elif "System Settings" in nav_choice:
            page_system_settings(service)


if __name__ == "__main__":
    main()
