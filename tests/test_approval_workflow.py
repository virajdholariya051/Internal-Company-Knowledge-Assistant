"""Unit tests for document approval lifecycle: Pending, Approved, Rejected, and Revoked states."""

import tempfile
from pathlib import Path
import pytest

from backend.authentication import create_user, hash_password
from backend.database import get_db_connection, init_db, seed_initial_data
from backend.knowledge_service import KnowledgeService

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_documents"


@pytest.fixture
def workflow_setup():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    seed_initial_data(db_path, admin_password_hash=hash_password("Admin@12345"))

    service = KnowledgeService(db_path=db_path)
    admin = {
        "user_id": "user_admin_001",
        "username": "admin",
        "role": "Administrator",
        "status": "Active",
        "group_ids": ["grp_general", "grp_hr", "grp_eng", "grp_finance", "grp_exec"],
    }
    emp = create_user("alice.emp", "PassAlice123", "Alice Employee", "Employee", db_path=db_path)
    reviewer = create_user("charlie.rev", "PassChar123", "Charlie Reviewer", "Reviewer", db_path=db_path)

    yield service, admin, reviewer, emp, db_path
    Path(db_path).unlink(missing_ok=True)


def test_complete_approval_workflow(workflow_setup):
    """Test full document lifecycle: Pending -> Approved -> Searchable -> Revoked -> Unsearchable."""
    service, admin, reviewer, emp, db_path = workflow_setup

    # 1. Employee uploads document -> Must be in 'Pending Approval'
    faq_path = SAMPLE_DIR / "FAQ_Remote_Work_and_Leave.txt"
    with open(faq_path, "rb") as f:
        upload_res = service.upload_and_process_document(
            filename="FAQ_Remote_Work_and_Leave.txt",
            content_bytes=f.read(),
            title="Remote Work Guidelines",
            category="cat_faq",
            classification="Public",
            user=emp,
            auto_approve_if_admin=False,
        )

    assert upload_res["success"] is True
    doc_id = upload_res["document_id"]
    assert upload_res["status"] == "Pending Approval"

    # Query before approval: must not find answer
    ans_pending = service.ask_question("What are the core collaboration hours?", emp)
    assert ans_pending.status == "insufficient_evidence"

    # 2. Employee attempts to approve -> Must raise PermissionError
    with pytest.raises(PermissionError):
        service.approve_document(doc_id, emp)

    # 3. Reviewer approves document
    ok = service.approve_document(doc_id, reviewer, notes="Verified compliant with HR standards.")
    assert ok is True

    # Query after approval: must succeed!
    ans_approved = service.ask_question("What are the core collaboration hours?", emp)
    assert ans_approved.status == "answered"
    assert len(ans_approved.citations) > 0

    # 4. Administrator revokes approval
    rev_ok = service.revoke_document_approval(doc_id, admin, notes="Revoked pending legal update.")
    assert rev_ok is True

    # Query after revoking: must immediately return insufficient evidence
    ans_revoked = service.ask_question("What are the core collaboration hours?", emp)
    assert ans_revoked.status == "insufficient_evidence"

    # Verify audit history
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT action FROM document_review_history WHERE document_id = ? ORDER BY created_at ASC;", (doc_id,))
        actions = [r["action"] for r in cursor.fetchall()]

    assert "Submitted" in actions
    assert "Approved" in actions
    assert "Revoked" in actions


def test_rejection_workflow(workflow_setup):
    """Test rejecting a document with a mandatory reason."""
    service, admin, reviewer, emp, db_path = workflow_setup

    faq_path = SAMPLE_DIR / "FAQ_Remote_Work_and_Leave.txt"
    with open(faq_path, "rb") as f:
        upload_res = service.upload_and_process_document(
            filename="FAQ_Remote_Work_and_Leave.txt",
            content_bytes=f.read(),
            title="Draft FAQ",
            category="cat_faq",
            classification="Public",
            user=emp,
            auto_approve_if_admin=False,
        )
    doc_id = upload_res["document_id"]

    # Reject without reason must raise ValueError
    with pytest.raises(ValueError):
        service.reject_document(doc_id, reviewer, rejection_reason="")

    # Reject with proper reason
    rej_ok = service.reject_document(
        doc_id,
        reviewer,
        rejection_reason="Contains obsolete stipend figures.",
    )
    assert rej_ok is True

    # Check database status
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, rejection_reason FROM documents WHERE document_id = ?;", (doc_id,))
        row = cursor.fetchone()
    assert row["status"] == "Rejected"
    assert "obsolete stipend" in row["rejection_reason"]
