"""Unit tests for SQLite database initialization, schema integrity, and relationships."""

import sqlite3
import tempfile
from pathlib import Path
import pytest

from backend.database import (
    get_db_connection,
    init_db,
    seed_initial_data,
)


@pytest.fixture
def temp_db():
    """Create a temporary database file for isolated testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    yield db_path
    Path(db_path).unlink(missing_ok=True)


def test_database_initialization(temp_db):
    """Test that all required tables and indexes are created properly."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

    expected_tables = {
        "users",
        "access_groups",
        "user_groups",
        "document_categories",
        "documents",
        "document_permissions",
        "document_chunks",
        "question_history",
        "document_review_history",
    }
    assert expected_tables.issubset(tables)


def test_foreign_key_enforcement(temp_db):
    """Test that SQLite foreign key enforcement is active and blocks orphaned records."""
    with pytest.raises(sqlite3.IntegrityError):
        with get_db_connection(temp_db) as conn:
            cursor = conn.cursor()
            # Inserting a chunk referencing a non-existent document must fail
            cursor.execute(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, chunk_index, chunk_text, page_number,
                    section_heading, word_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                ("c_test", "non_existent_doc_id", 0, "Test chunk", 1, "Sec", 10, "2026-01-01T00:00:00Z"),
            )


def test_seed_initial_data(temp_db):
    """Test that standard categories and groups are seeded without duplicates."""
    seed_initial_data(temp_db, admin_password_hash="test_admin_hash")

    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM document_categories;")
        cat_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM access_groups;")
        grp_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin';")
        admin_count = cursor.fetchone()[0]

    assert cat_count >= 5
    assert grp_count >= 5
    assert admin_count == 1

    # Running seed a second time must be idempotent (no duplicate key errors)
    seed_initial_data(temp_db, admin_password_hash="test_admin_hash")
