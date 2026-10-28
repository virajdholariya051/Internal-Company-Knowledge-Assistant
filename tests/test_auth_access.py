"""Unit tests for authentication, password hashing, and access control enforcement."""

import tempfile
from pathlib import Path
import pytest

from backend.access_control import (
    can_manage_users,
    can_review_documents,
    can_upload_documents,
    can_user_access_document,
    get_authorized_document_ids,
    is_admin,
)
from backend.authentication import (
    authenticate_user,
    create_user,
    hash_password,
    initialize_admin_if_empty,
    update_user_role,
    update_user_status,
    verify_password,
)
from backend.database import get_db_connection, init_db, seed_initial_data


@pytest.fixture
def auth_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    seed_initial_data(db_path, admin_password_hash=hash_password("Admin@12345"))
    yield db_path
    Path(db_path).unlink(missing_ok=True)


def test_password_hashing():
    """Verify that password hashing produces salted hashes and verifies accurately."""
    pwd = "SecureCompanyPassword2026!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password("", hashed) is False


def test_user_creation_and_authentication(auth_db):
    """Test user registration and successful authentication."""
    user = create_user(
        username="john.doe",
        password="Password123",
        full_name="John Doe",
        role="Employee",
        group_ids=["grp_eng"],
        db_path=auth_db,
    )
    assert user["username"] == "john.doe"
    assert user["role"] == "Employee"

    # Authenticate with correct credentials
    auth_result = authenticate_user("john.doe", "Password123", db_path=auth_db)
    assert auth_result is not None
    assert auth_result["user_id"] == user["user_id"]
    assert "grp_eng" in auth_result["group_ids"]
    assert "grp_general" in auth_result["group_ids"]

    # Authenticate with bad password
    bad_auth = authenticate_user("john.doe", "WrongPass", db_path=auth_db)
    assert bad_auth is None


def test_rbac_permissions(auth_db):
    """Test role hierarchy permissions."""
    admin = authenticate_user("admin", "Admin@12345", db_path=auth_db)
    emp = create_user("jane.emp", "EmpPass123", "Jane Employee", "Employee", db_path=auth_db)
    reviewer = create_user("mark.rev", "RevPass123", "Mark Reviewer", "Reviewer", db_path=auth_db)

    assert is_admin(admin) is True
    assert is_admin(emp) is False
    assert is_admin(reviewer) is False

    assert can_manage_users(admin) is True
    assert can_manage_users(emp) is False
    assert can_manage_users(reviewer) is False

    assert can_review_documents(admin) is True
    assert can_review_documents(reviewer) is True
    assert can_review_documents(emp) is False


def test_document_access_isolation(auth_db):
    """Test that employees cannot access restricted or confidential documents unless authorized."""
    admin = authenticate_user("admin", "Admin@12345", db_path=auth_db)
    emp_eng = create_user("eng_user", "EngPass123", "Eng User", "Employee", ["grp_eng"], db_path=auth_db)
    emp_hr = create_user("hr_user", "HrPass123", "HR User", "Employee", ["grp_hr"], db_path=auth_db)

    # Insert test documents in database: Public, Restricted to Engineering, Confidential to Executive
    with get_db_connection(auth_db) as conn:
        cursor = conn.cursor()
        # 1. Public approved
        cursor.execute(
            """
            INSERT INTO documents (document_id, title, category, classification, original_filename,
                file_hash, file_type, file_path, file_size, status, uploaded_by, uploaded_at)
            VALUES ('doc_public', 'Public SOP', 'cat_sop', 'Public', 'sop.txt', 'hash1', 'txt', '/tmp/sop.txt', 100, 'Approved', ?, '2026-01-01');
            """,
            (admin["user_id"],),
        )
        # 2. Restricted to Engineering
        cursor.execute(
            """
            INSERT INTO documents (document_id, title, category, classification, original_filename,
                file_hash, file_type, file_path, file_size, status, uploaded_by, uploaded_at)
            VALUES ('doc_eng', 'Engineering Architecture', 'cat_project', 'Restricted', 'arch.txt', 'hash2', 'txt', '/tmp/arch.txt', 100, 'Approved', ?, '2026-01-01');
            """,
            (admin["user_id"],),
        )
        cursor.execute(
            "INSERT INTO document_permissions (permission_id, document_id, group_id, granted_at) VALUES ('p1', 'doc_eng', 'grp_eng', '2026-01-01');"
        )
        # 3. Confidential to Executive
        cursor.execute(
            """
            INSERT INTO documents (document_id, title, category, classification, original_filename,
                file_hash, file_type, file_path, file_size, status, uploaded_by, uploaded_at)
            VALUES ('doc_exec', 'Executive Salaries', 'cat_policy', 'Confidential', 'sal.txt', 'hash3', 'txt', '/tmp/sal.txt', 100, 'Approved', ?, '2026-01-01');
            """,
            (admin["user_id"],),
        )
        cursor.execute(
            "INSERT INTO document_permissions (permission_id, document_id, group_id, granted_at) VALUES ('p2', 'doc_exec', 'grp_exec', '2026-01-01');"
        )

    # Public document: Both employees and admin can access
    assert can_user_access_document(admin, "doc_public", db_path=auth_db) is True
    assert can_user_access_document(emp_eng, "doc_public", db_path=auth_db) is True
    assert can_user_access_document(emp_hr, "doc_public", db_path=auth_db) is True

    # Engineering Restricted document: eng_user and admin can access, hr_user cannot
    assert can_user_access_document(admin, "doc_eng", db_path=auth_db) is True
    assert can_user_access_document(emp_eng, "doc_eng", db_path=auth_db) is True
    assert can_user_access_document(emp_hr, "doc_eng", db_path=auth_db) is False

    # Confidential document: Admin can access, neither regular employee can access
    assert can_user_access_document(admin, "doc_exec", db_path=auth_db) is True
    assert can_user_access_document(emp_eng, "doc_exec", db_path=auth_db) is False
    assert can_user_access_document(emp_hr, "doc_exec", db_path=auth_db) is False
