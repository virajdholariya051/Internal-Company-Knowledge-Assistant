"""Access control and authorization enforcement for Internal Company Knowledge Assistant.

Enforces Role-Based Access Control (RBAC) and Document Classification Rules
(Public, Restricted, Confidential) at the database and query layer.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Set

from backend.database import get_db_connection


def is_admin(user: Dict[str, Any]) -> bool:
    """Check if the user has the Administrator role."""
    return user is not None and user.get("role") == "Administrator"


def is_reviewer(user: Dict[str, Any]) -> bool:
    """Check if the user is an Administrator or Reviewer."""
    return user is not None and user.get("role") in ("Administrator", "Reviewer")


def can_review_documents(user: Dict[str, Any]) -> bool:
    """Check if the user has permission to review, approve, or reject documents."""
    return is_reviewer(user)


def can_manage_users(user: Dict[str, Any]) -> bool:
    """Check if user has permission to manage users and access roles."""
    return is_admin(user)


def can_upload_documents(user: Dict[str, Any]) -> bool:
    """Check if user has permission to upload company documents."""
    # Active Employees, Reviewers, and Administrators can upload documents for approval
    return user is not None and user.get("status") == "Active"


def get_authorized_document_ids(user: Dict[str, Any], db_path: Optional[str] = None) -> Set[str]:
    """Retrieve set of all document IDs that the given user is authorized to read.

    Rules:
    - Inactive/disabled users have no document access.
    - Administrators have access to all approved documents.
    - Ordinary users can access:
      1. 'Public' documents (classification = 'Public').
      2. 'Restricted' documents where user belongs to at least one group assigned to the document.
      3. 'Confidential' documents where user belongs to an explicitly authorized group assigned to the document.
    - Note: Only 'Approved' documents are returned for normal retrieval/reading.
      Pending, Rejected, or Revoked documents are excluded unless explicitly bypassed for administrative review.

    Args:
        user: Authenticated user dictionary containing 'user_id', 'role', and 'group_ids'.
        db_path: Optional database path.

    Returns:
        Set[str]: Set of authorized document IDs.
    """
    if not user or user.get("status") != "Active":
        return set()

    user_id = user["user_id"]
    user_role = user.get("role")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Administrators can view all approved documents
        if user_role == "Administrator":
            cursor.execute(
                "SELECT document_id FROM documents WHERE status = 'Approved';"
            )
            return {row["document_id"] for row in cursor.fetchall()}

        # For Employees and Reviewers:
        # 1. Public approved documents
        cursor.execute(
            """
            SELECT document_id FROM documents
            WHERE status = 'Approved' AND classification = 'Public';
            """
        )
        authorized_ids = {row["document_id"] for row in cursor.fetchall()}

        # 2. Restricted or Confidential documents authorized via user_groups -> document_permissions
        cursor.execute(
            """
            SELECT DISTINCT d.document_id
            FROM documents d
            JOIN document_permissions dp ON d.document_id = dp.document_id
            JOIN user_groups ug ON dp.group_id = ug.group_id
            WHERE d.status = 'Approved'
              AND ug.user_id = ?;
            """,
            (user_id,),
        )
        for row in cursor.fetchall():
            authorized_ids.add(row["document_id"])

        return authorized_ids


def can_user_access_document(user: Dict[str, Any], document_id: str, db_path: Optional[str] = None) -> bool:
    """Check if a specific user can access a specific document."""
    if not user or user.get("status") != "Active":
        return False

    if is_admin(user):
        return True

    authorized_ids = get_authorized_document_ids(user, db_path=db_path)
    return document_id in authorized_ids


def filter_authorized_chunks_query(
    user: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    """Build a parameterized SQL clause and params to select only chunks from authorized approved documents.

    This ensures that access control is enforced at the database layer before any retrieval or
    similarity ranking occurs.

    Args:
        user: Authenticated user dictionary.
        db_path: Optional database path.

    Returns:
        Tuple[str, List[Any]]: (sql_query, parameters)
    """
    authorized_ids = get_authorized_document_ids(user, db_path=db_path)
    if not authorized_ids:
        # No authorized documents: return a query that produces 0 rows
        return "SELECT chunk_id, document_id, chunk_index, chunk_text, page_number, section_heading FROM document_chunks WHERE 1 = 0", []

    placeholders = ",".join(["?"] * len(authorized_ids))
    sql = f"""
        SELECT c.chunk_id, c.document_id, c.chunk_index, c.chunk_text, c.page_number, c.section_heading,
               d.title as doc_title, d.category as doc_category, d.classification as doc_classification
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.document_id
        WHERE c.document_id IN ({placeholders})
          AND d.status = 'Approved';
    """
    return sql, list(authorized_ids)
