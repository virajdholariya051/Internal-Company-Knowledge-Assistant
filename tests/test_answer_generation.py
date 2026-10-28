"""Unit tests for grounded answer generation, citations, and insufficient-evidence reporting."""

import tempfile
from pathlib import Path
import pytest

from backend.authentication import create_user, hash_password
from backend.database import init_db, seed_initial_data
from backend.knowledge_service import KnowledgeService

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_documents"


@pytest.fixture
def qa_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    seed_initial_data(db_path, admin_password_hash=hash_password("Admin@12345"))

    service = KnowledgeService(db_path=db_path)
    admin_user = {
        "user_id": "user_admin_001",
        "username": "admin",
        "role": "Administrator",
        "status": "Active",
        "group_ids": ["grp_general", "grp_hr", "grp_eng", "grp_finance", "grp_exec"],
    }

    # Upload Public FAQ
    faq_path = SAMPLE_DIR / "FAQ_Remote_Work_and_Leave.txt"
    with open(faq_path, "rb") as f:
        service.upload_and_process_document(
            filename="FAQ_Remote_Work_and_Leave.txt",
            content_bytes=f.read(),
            title="Remote Work & Leave Policy FAQ",
            category="cat_faq",
            classification="Public",
            user=admin_user,
            auto_approve_if_admin=True,
        )

    # Upload Confidential Executive Compensation
    conf_path = SAMPLE_DIR / "CONFIDENTIAL_Executive_Compensation_2026.txt"
    with open(conf_path, "rb") as f:
        service.upload_and_process_document(
            filename="CONFIDENTIAL_Executive_Compensation_2026.txt",
            content_bytes=f.read(),
            title="Executive Compensation 2026",
            category="cat_policy",
            classification="Confidential",
            target_group_ids=["grp_exec"],
            user=admin_user,
            auto_approve_if_admin=True,
        )

    # Create ordinary employee without Executive group
    emp_user = create_user("bob.dev", "BobPass123", "Bob Developer", "Employee", ["grp_eng"], db_path=db_path)

    yield service, admin_user, emp_user, db_path
    Path(db_path).unlink(missing_ok=True)


def test_grounded_answer_generation(qa_service):
    """Test that a grounded answer is produced with genuine citations for a valid question."""
    service, admin_user, emp_user, _ = qa_service

    answer = service.ask_question("What is the home office technology stipend amount?", emp_user)
    assert answer.status == "answered"
    assert "$500" in answer.answer_text or "500" in answer.answer_text
    assert len(answer.citations) > 0

    top_citation = answer.citations[0]
    assert top_citation.document_title == "Remote Work & Leave Policy FAQ"
    assert len(top_citation.supporting_excerpt) > 10


def test_insufficient_evidence_behavior(qa_service):
    """Test that the assistant explicitly reports no evidence found on unsupported topics."""
    service, admin_user, emp_user, _ = qa_service

    answer = service.ask_question("What are the quarterly sales targets for the Tokyo office?", emp_user)
    assert answer.status == "insufficient_evidence"
    assert "No sufficient evidence" in answer.answer_text
    assert len(answer.citations) == 0


def test_confidential_document_isolation(qa_service):
    """Test that ordinary employees cannot retrieve or cite confidential executive documents."""
    service, admin_user, emp_user, _ = qa_service

    query = "What is the maximum executive performance incentive bonus pool?"

    # 1. Ordinary employee asking: Must receive insufficient evidence / 0 citations
    emp_answer = service.ask_question(query, emp_user)
    assert emp_answer.status == "insufficient_evidence"
    assert len(emp_answer.citations) == 0

    # 2. Executive / Administrator asking: Receives authorized grounded answer with citation
    admin_answer = service.ask_question(query, admin_user)
    assert admin_answer.status == "answered"
    assert "$2,500,000" in admin_answer.answer_text or "2,500,000" in admin_answer.answer_text
    assert len(admin_answer.citations) > 0
    assert "Executive Compensation" in admin_answer.citations[0].document_title
