"""Knowledge service orchestrator for Internal Company Knowledge Assistant.

Coordinates document uploading, validation, chunking, database persistence,
document review lifecycle (Approve, Reject, Revoke), TF-IDF index updates,
user-scoped question answering, and Q&A history tracking.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.access_control import (
    can_manage_users,
    can_review_documents,
    can_upload_documents,
    can_user_access_document,
    is_admin,
)
from backend.answer_generator import AnswerGenerator, GeneratedAnswer
from backend.database import get_current_timestamp, get_db_connection
from backend.document_processor import (
    ExtractionResult,
    compute_file_hash,
    extract_document,
    save_uploaded_file,
)
from backend.retriever import RetrievalResult, get_retriever
from backend.text_chunker import chunk_document_sections


class KnowledgeService:
    """Service layer exposing core business logic to the UI and API."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        self.answer_generator = AnswerGenerator()

    # -------------------------------------------------------------------------
    # Document Upload & Ingestion
    # -------------------------------------------------------------------------
    def upload_and_process_document(
        self,
        filename: str,
        content_bytes: bytes,
        title: str,
        category: str,
        classification: str,
        user: Dict[str, Any],
        target_group_ids: Optional[List[str]] = None,
        auto_approve_if_admin: bool = False,
    ) -> Dict[str, Any]:
        """Validate, extract, chunk, and register a new document in Pending Approval status.

        Args:
            filename: Original file name.
            content_bytes: File binary payload.
            title: User-defined display title.
            category: Selected document category.
            classification: 'Public', 'Restricted', or 'Confidential'.
            user: Authenticated user initiating upload.
            target_group_ids: Access group IDs allowed to view this document if Restricted/Confidential.
            auto_approve_if_admin: If true and user is Administrator, auto-approves immediately.

        Returns:
            Dict[str, Any]: Ingestion status, doc_id, and extracted stats.
        """
        if not can_upload_documents(user):
            raise PermissionError("User is not authorized to upload documents.")

        title = title.strip()
        if not title:
            raise ValueError("Document title is required.")

        if classification not in ("Public", "Restricted", "Confidential"):
            raise ValueError(f"Invalid classification: {classification}")

        # Check duplicate content hash
        file_hash = compute_file_hash(content_bytes)
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT document_id, title, status FROM documents WHERE file_hash = ?;",
                (file_hash,),
            )
            dup = cursor.fetchone()
            if dup:
                return {
                    "success": False,
                    "error": f"Duplicate file detected. This document already exists as '{dup['title']}' (Status: {dup['status']}).",
                    "duplicate_id": dup["document_id"],
                }

        # Extract text and sections
        extract_res = extract_document(filename, content_bytes)
        if not extract_res.success:
            return {
                "success": False,
                "error": extract_res.error_message or "Extraction failed.",
                "is_scanned_pdf": extract_res.is_scanned_pdf,
            }

        # Save binary file safely with unique internal filename
        internal_doc_id, saved_path = save_uploaded_file(content_bytes, filename)

        # Chunk extracted sections
        chunks = chunk_document_sections(extract_res.sections, internal_doc_id)
        if not chunks:
            return {
                "success": False,
                "error": "Document contains no processable text chunks.",
            }

        now = get_current_timestamp()
        initial_status = "Approved" if (auto_approve_if_admin and is_admin(user)) else "Pending Approval"
        reviewed_by = user["user_id"] if initial_status == "Approved" else None
        reviewed_at = now if initial_status == "Approved" else None

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert document record
            cursor.execute(
                """
                INSERT INTO documents (
                    document_id, title, category, classification,
                    original_filename, file_hash, file_type, file_path, file_size,
                    status, rejection_reason, uploaded_by, uploaded_at,
                    reviewed_by, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?);
                """,
                (
                    internal_doc_id,
                    title,
                    category,
                    classification,
                    filename,
                    file_hash,
                    extract_res.file_type,
                    str(saved_path),
                    extract_res.file_size,
                    initial_status,
                    user["user_id"],
                    now,
                    reviewed_by,
                    reviewed_at,
                ),
            )

            # Insert document permissions if Restricted or Confidential
            if classification in ("Restricted", "Confidential") and target_group_ids:
                for gid in target_group_ids:
                    perm_id = f"perm_{uuid.uuid4().hex[:12]}"
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO document_permissions (permission_id, document_id, group_id, granted_at)
                        VALUES (?, ?, ?, ?);
                        """,
                        (perm_id, internal_doc_id, gid, now),
                    )

            # Bulk insert chunks
            chunk_records = [
                (
                    c.chunk_id,
                    c.document_id,
                    c.chunk_index,
                    c.chunk_text,
                    c.page_number,
                    c.section_heading,
                    c.word_count,
                    now,
                )
                for c in chunks
            ]
            cursor.executemany(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, chunk_index, chunk_text,
                    page_number, section_heading, word_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                chunk_records,
            )

            # Log review action
            review_id = f"rev_{uuid.uuid4().hex[:12]}"
            review_action = "Approved" if initial_status == "Approved" else "Submitted"
            cursor.execute(
                """
                INSERT INTO document_review_history (review_id, document_id, action, reviewer_id, review_notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    review_id,
                    internal_doc_id,
                    review_action,
                    user["user_id"],
                    "Auto-approved by Administrator" if initial_status == "Approved" else "Submitted for approval",
                    now,
                ),
            )

        # If auto-approved, rebuild index
        if initial_status == "Approved":
            retriever = get_retriever(self.db_path)
            retriever.build_index()

        return {
            "success": True,
            "document_id": internal_doc_id,
            "status": initial_status,
            "title": title,
            "total_chunks": len(chunks),
            "total_words": extract_res.total_words,
            "pages_or_sections": extract_res.total_pages_or_sections,
        }

    # -------------------------------------------------------------------------
    # Approval Workflow (Approve, Reject, Revoke)
    # -------------------------------------------------------------------------
    def approve_document(
        self,
        document_id: str,
        reviewer_user: Dict[str, Any],
        notes: Optional[str] = None,
    ) -> bool:
        """Approve a document and index its chunks into the retrieval engine."""
        if not can_review_documents(reviewer_user):
            raise PermissionError("User is not authorized to approve documents.")

        now = get_current_timestamp()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE documents
                SET status = 'Approved',
                    rejection_reason = NULL,
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE document_id = ?;
                """,
                (reviewer_user["user_id"], now, document_id),
            )
            if cursor.rowcount == 0:
                return False

            # Add to review history
            cursor.execute(
                """
                INSERT INTO document_review_history (review_id, document_id, action, reviewer_id, review_notes, created_at)
                VALUES (?, ?, 'Approved', ?, ?, ?);
                """,
                (f"rev_{uuid.uuid4().hex[:12]}", document_id, reviewer_user["user_id"], notes or "Document approved.", now),
            )

        # Rebuild retriever index
        retriever = get_retriever(self.db_path)
        retriever.build_index()
        return True

    def reject_document(
        self,
        document_id: str,
        reviewer_user: Dict[str, Any],
        rejection_reason: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Reject a document with a recorded reason, ensuring it cannot be indexed or retrieved."""
        if not can_review_documents(reviewer_user):
            raise PermissionError("User is not authorized to reject documents.")

        if not rejection_reason or not rejection_reason.strip():
            raise ValueError("A clear rejection reason must be provided.")

        now = get_current_timestamp()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE documents
                SET status = 'Rejected',
                    rejection_reason = ?,
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE document_id = ?;
                """,
                (rejection_reason.strip(), reviewer_user["user_id"], now, document_id),
            )
            if cursor.rowcount == 0:
                return False

            cursor.execute(
                """
                INSERT INTO document_review_history (review_id, document_id, action, reviewer_id, review_notes, created_at)
                VALUES (?, ?, 'Rejected', ?, ?, ?);
                """,
                (
                    f"rev_{uuid.uuid4().hex[:12]}",
                    document_id,
                    reviewer_user["user_id"],
                    f"Reason: {rejection_reason.strip()}. Notes: {notes or ''}",
                    now,
                ),
            )

        # Rebuild retriever index to ensure no chunks remain searchable
        retriever = get_retriever(self.db_path)
        retriever.build_index()
        return True

    def revoke_document_approval(
        self,
        document_id: str,
        reviewer_user: Dict[str, Any],
        notes: Optional[str] = None,
    ) -> bool:
        """Revoke prior approval, immediately removing document from retrieval results."""
        if not can_review_documents(reviewer_user):
            raise PermissionError("User is not authorized to revoke document approval.")

        now = get_current_timestamp()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE documents
                SET status = 'Revoked',
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE document_id = ?;
                """,
                (reviewer_user["user_id"], now, document_id),
            )
            if cursor.rowcount == 0:
                return False

            cursor.execute(
                """
                INSERT INTO document_review_history (review_id, document_id, action, reviewer_id, review_notes, created_at)
                VALUES (?, ?, 'Revoked', ?, ?, ?);
                """,
                (f"rev_{uuid.uuid4().hex[:12]}", document_id, reviewer_user["user_id"], notes or "Approval revoked.", now),
            )

        # Rebuild retriever index
        retriever = get_retriever(self.db_path)
        retriever.build_index()
        return True

    # -------------------------------------------------------------------------
    # Q&A Answering & Question History
    # -------------------------------------------------------------------------
    def ask_question(
        self,
        query: str,
        user: Dict[str, Any],
        top_k: int = 5,
        min_score: float = 0.12,
        log_history: bool = True,
    ) -> GeneratedAnswer:
        """Process a natural language question with authorized retrieval and citation generation.

        Args:
            query: Question text.
            user: Authenticated user.
            top_k: Max chunks to retrieve.
            min_score: Cosine similarity cutoff.
            log_history: Whether to persist into user's private question history.

        Returns:
            GeneratedAnswer: Synthesized grounded answer and citations.
        """
        retriever = get_retriever(self.db_path)
        results = retriever.retrieve(query, user, top_k=top_k, min_score=min_score)
        answer = self.answer_generator.generate_answer(query, results, user, db_path=self.db_path)

        # Persist to private user question history if requested and not empty
        if log_history and user and (query or "").strip():
            now = get_current_timestamp()
            history_id = f"hist_{uuid.uuid4().hex[:12]}"
            citations_data = [c.to_dict() for c in answer.citations]
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO question_history (
                        history_id, user_id, question_text, answer_text,
                        evidence_count, citations_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        history_id,
                        user["user_id"],
                        query.strip(),
                        answer.answer_text,
                        answer.evidence_count,
                        json.dumps(citations_data),
                        now,
                    ),
                )

        return answer

    def get_user_question_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch question history strictly belonging to the specified user."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT history_id, question_text, answer_text, evidence_count,
                       citations_json, created_at
                FROM question_history
                WHERE user_id = ?
                ORDER BY created_at DESC;
                """,
                (user_id,),
            )
            rows = []
            for r in cursor.fetchall():
                item = dict(r)
                try:
                    item["citations"] = json.loads(item["citations_json"])
                except Exception:
                    item["citations"] = []
                rows.append(item)
            return rows

    def clear_user_question_history(self, user_id: str) -> int:
        """Clear all Q&A history records for a specific user."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM question_history WHERE user_id = ?;", (user_id,))
            return cursor.rowcount

    # -------------------------------------------------------------------------
    # Document Management & Inquiries
    # -------------------------------------------------------------------------
    def list_documents(
        self,
        user: Dict[str, Any],
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List documents visible to the user, respecting security rules."""
        if not user or user.get("status") != "Active":
            return []

        user_is_admin = is_admin(user)
        user_is_rev = can_review_documents(user)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            query = """
                SELECT d.document_id, d.title, d.category, d.classification,
                       d.original_filename, d.file_type, d.file_size, d.status,
                       d.rejection_reason, d.uploaded_by, d.uploaded_at,
                       d.reviewed_by, d.reviewed_at,
                       u.full_name as uploader_name,
                       (SELECT COUNT(*) FROM document_chunks WHERE document_id = d.document_id) as chunk_count
                FROM documents d
                LEFT JOIN users u ON d.uploaded_by = u.user_id
                WHERE 1 = 1
            """
            params: List[Any] = []

            # If ordinary employee (not admin/reviewer):
            # Can only see 'Approved' documents they are authorized for, OR documents they uploaded themselves
            if not user_is_admin and not user_is_rev:
                query += """
                    AND (
                        (d.status = 'Approved' AND (
                            d.classification = 'Public'
                            OR d.document_id IN (
                                SELECT dp.document_id FROM document_permissions dp
                                JOIN user_groups ug ON dp.group_id = ug.group_id
                                WHERE ug.user_id = ?
                            )
                        ))
                        OR d.uploaded_by = ?
                    )
                """
                params.extend([user["user_id"], user["user_id"]])

            if status_filter:
                query += " AND d.status = ?"
                params.append(status_filter)

            if category_filter:
                query += " AND d.category = ?"
                params.append(category_filter)

            query += " ORDER BY d.uploaded_at DESC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_document_chunks_for_preview(
        self,
        document_id: str,
        user: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get document chunks for preview if authorized."""
        if not can_user_access_document(user, document_id, db_path=self.db_path):
            raise PermissionError("Access denied: You are not authorized to preview this document.")

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT chunk_id, chunk_index, chunk_text, page_number, section_heading, word_count
                FROM document_chunks
                WHERE document_id = ?
                ORDER BY chunk_index ASC;
                """,
                (document_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def delete_document(self, document_id: str, admin_user: Dict[str, Any]) -> bool:
        """Permanently delete a document, its chunks, permissions, and file from storage. Admin only."""
        if not is_admin(admin_user):
            raise PermissionError("Only an Administrator can delete documents.")

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM documents WHERE document_id = ?;", (document_id,))
            doc = cursor.fetchone()
            if not doc:
                return False

            # Delete file from storage safely
            if doc["file_path"]:
                try:
                    p = Path(doc["file_path"])
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

            cursor.execute("DELETE FROM documents WHERE document_id = ?;", (document_id,))

        # Rebuild retrieval index
        retriever = get_retriever(self.db_path)
        retriever.build_index()
        return True

    def get_categories(self) -> List[Dict[str, Any]]:
        """List all document categories."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT category_id, category_name, description FROM document_categories ORDER BY category_name;")
            return [dict(r) for r in cursor.fetchall()]

    def add_category(self, name: str, description: str, admin_user: Dict[str, Any]) -> str:
        """Create a custom document category. Admin only."""
        if not is_admin(admin_user):
            raise PermissionError("Only an Administrator can create document categories.")

        name = name.strip()
        if not name:
            raise ValueError("Category name is required.")

        cat_id = f"cat_{uuid.uuid4().hex[:8]}"
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO document_categories (category_id, category_name, description) VALUES (?, ?, ?);",
                (cat_id, name, description.strip()),
            )
        return cat_id

    def get_access_groups(self) -> List[Dict[str, Any]]:
        """List all access groups."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT group_id, group_name, description FROM access_groups ORDER BY group_name;")
            return [dict(r) for r in cursor.fetchall()]
