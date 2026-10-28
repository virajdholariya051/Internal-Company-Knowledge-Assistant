"""Database management and schema definitions for Internal Company Knowledge Assistant.

Supports SQLite with foreign keys enabled, parameterized queries, schema initialization,
and seeding for standard categories, access groups, and initial administrator.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

# Default database location inside data/ directory
DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "assistant.db"


def get_current_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db_connection(db_path: Optional[str | Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with foreign keys enabled and row factory set.

    Args:
        db_path: Path to SQLite database file or ':memory:'. If None, uses DEFAULT_DB_PATH.

    Yields:
        sqlite3.Connection: Active database connection.
    """
    target_path = Path(db_path) if db_path and db_path != ":memory:" else db_path
    if target_path and target_path != ":memory:":
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn_target = str(target_path)
    elif db_path == ":memory:":
        conn_target = ":memory:"
    else:
        DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
        conn_target = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(conn_target, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str | Path] = None) -> None:
    """Initialize all database tables, constraints, and indexes.

    Args:
        db_path: Optional database path.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Users table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Administrator', 'Employee', 'Reviewer')),
                status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Disabled')),
                created_at TEXT NOT NULL
            );
            """
        )

        # 2. Access groups table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS access_groups (
                group_id TEXT PRIMARY KEY,
                group_name TEXT UNIQUE NOT NULL,
                description TEXT
            );
            """
        )

        # 3. User access groups mapping
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_groups (
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                PRIMARY KEY (user_id, group_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES access_groups(group_id) ON DELETE CASCADE
            );
            """
        )

        # 4. Document categories table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_categories (
                category_id TEXT PRIMARY KEY,
                category_name TEXT UNIQUE NOT NULL,
                description TEXT
            );
            """
        )

        # 5. Documents table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                classification TEXT NOT NULL CHECK(classification IN ('Public', 'Restricted', 'Confidential')),
                original_filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_type TEXT NOT NULL CHECK(file_type IN ('pdf', 'docx', 'txt')),
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending Approval' CHECK(status IN ('Pending Approval', 'Approved', 'Rejected', 'Revoked')),
                rejection_reason TEXT,
                uploaded_by TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                FOREIGN KEY (uploaded_by) REFERENCES users(user_id) ON DELETE RESTRICT,
                FOREIGN KEY (reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL
            );
            """
        )

        # 6. Document access permissions table (for restricted/confidential documents)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_permissions (
                permission_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES access_groups(group_id) ON DELETE CASCADE,
                UNIQUE(document_id, group_id)
            );
            """
        )

        # 7. Document chunks table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                page_number INTEGER,
                section_heading TEXT,
                word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                UNIQUE(document_id, chunk_index)
            );
            """
        )

        # 8. Question & Answer History table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS question_history (
                history_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                citations_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            """
        )

        # 9. Document review history table (Audit trail)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_review_history (
                review_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('Submitted', 'Approved', 'Rejected', 'Revoked')),
                reviewer_id TEXT NOT NULL,
                review_notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                FOREIGN KEY (reviewer_id) REFERENCES users(user_id) ON DELETE RESTRICT
            );
            """
        )

        # Indexes for query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_classification ON documents(classification);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON question_history(user_id);")


def seed_initial_data(db_path: Optional[str | Path] = None, admin_password_hash: Optional[str] = None) -> None:
    """Seed initial categories, access groups, and an administrator account if they do not exist.

    Args:
        db_path: Optional database path.
        admin_password_hash: Hashed password for initial admin. If None, uses a default placeholder hash.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Seed standard document categories
        categories = [
            ("cat_sop", "Standard Operating Procedures (SOP)", "Official step-by-step operational instructions"),
            ("cat_faq", "Frequently Asked Questions (FAQ)", "Answers to common employee and client questions"),
            ("cat_service", "Service Descriptions", "Overview of company services, offerings, and specs"),
            ("cat_pricing", "Pricing Rules", "Rate cards, discount policies, tiers, and contractual pricing constraints"),
            ("cat_project", "Project Documentation", "Project charters, architectures, deliverables, and specs"),
            ("cat_policy", "Policies and Guidelines", "Corporate, HR, safety, compliance, and acceptable use policies"),
            ("cat_general", "General Reference", "Company encyclopedias, organizational charts, and manuals"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO document_categories (category_id, category_name, description)
            VALUES (?, ?, ?);
            """,
            categories,
        )

        # Seed standard access groups
        groups = [
            ("grp_general", "All Employees", "Default access group for company-wide general documents"),
            ("grp_hr", "Human Resources", "HR personnel, benefits, recruitment, and payroll documentation"),
            ("grp_eng", "Engineering & IT", "Technical architecture, infrastructure, and dev documentation"),
            ("grp_finance", "Finance & Accounting", "Financial statements, pricing exception logs, and billing"),
            ("grp_exec", "Executive Leadership", "Strategic board minutes, confidential contracts, executive memos"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO access_groups (group_id, group_name, description)
            VALUES (?, ?, ?);
            """,
            groups,
        )

        # Check if any admin exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator';")
        admin_count = cursor.fetchone()[0]

        if admin_count == 0 and admin_password_hash:
            admin_id = "user_admin_001"
            cursor.execute(
                """
                INSERT OR IGNORE INTO users (user_id, username, password_hash, full_name, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    admin_id,
                    "admin",
                    admin_password_hash,
                    "System Administrator",
                    "Administrator",
                    "Active",
                    get_current_timestamp(),
                ),
            )
            # Add admin to all groups
            for grp in groups:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO user_groups (user_id, group_id)
                    VALUES (?, ?);
                    """,
                    (admin_id, grp[0]),
                )
