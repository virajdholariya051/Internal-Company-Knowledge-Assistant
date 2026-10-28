"""Unit tests for TF-IDF retrieval accuracy, similarity ranking, and access filtering."""

import tempfile
from pathlib import Path
import pytest

from backend.authentication import create_user, hash_password
from backend.database import init_db, seed_initial_data
from backend.knowledge_service import KnowledgeService
from backend.retriever import TFIDFRetriever

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_documents"


@pytest.fixture
def populated_knowledge_service():
    """Create KnowledgeService with initialized test DB and approved sample documents."""
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

    # Upload & auto-approve FAQ document (Public)
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

    # Upload & auto-approve Pricing document (Public)
    pricing_path = SAMPLE_DIR / "Service_Cloud_Hosting_Pricing_Rules.docx"
    with open(pricing_path, "rb") as f:
        service.upload_and_process_document(
            filename="Service_Cloud_Hosting_Pricing_Rules.docx",
            content_bytes=f.read(),
            title="Cloud Hosting Pricing Rules",
            category="cat_pricing",
            classification="Public",
            user=admin_user,
            auto_approve_if_admin=True,
        )

    # Upload SOP document (Pending Approval - not yet approved)
    sop_path = SAMPLE_DIR / "SOP_IT_Incident_Management.pdf"
    with open(sop_path, "rb") as f:
        service.upload_and_process_document(
            filename="SOP_IT_Incident_Management.pdf",
            content_bytes=f.read(),
            title="IT Incident Management SOP",
            category="cat_sop",
            classification="Public",
            user=admin_user,
            auto_approve_if_admin=False,  # Kept Pending Approval!
        )

    yield service, admin_user, db_path
    Path(db_path).unlink(missing_ok=True)


def test_retrieval_accuracy_known_question(populated_knowledge_service):
    """Test that asking about core hours accurately retrieves the FAQ document chunk."""
    service, admin_user, db_path = populated_knowledge_service
    retriever = TFIDFRetriever(db_path=db_path)
    retriever.build_index()

    results = retriever.retrieve("What are the mandatory core collaboration hours?", admin_user)
    assert len(results) > 0
    top_result = results[0]
    assert "Remote Work" in top_result.document_title
    assert "10:00 AM" in top_result.chunk_text or "core window" in top_result.chunk_text
    assert top_result.similarity_score > 0.15


def test_retrieval_pricing_question(populated_knowledge_service):
    """Test retrieving volume contract discount rules from DOCX pricing document."""
    service, admin_user, db_path = populated_knowledge_service
    retriever = TFIDFRetriever(db_path=db_path)
    retriever.build_index()

    results = retriever.retrieve("What discount applies to a 12-month contract?", admin_user)
    assert len(results) > 0
    top_result = results[0]
    assert "Cloud Hosting" in top_result.document_title
    assert "15%" in top_result.chunk_text or "discount" in top_result.chunk_text


def test_pending_document_is_not_retrieved(populated_knowledge_service):
    """Test that documents in 'Pending Approval' status are never retrieved."""
    service, admin_user, db_path = populated_knowledge_service
    retriever = TFIDFRetriever(db_path=db_path)
    retriever.build_index()

    # The SOP document is Pending Approval, so searching for Severity 1 escalation must yield 0 results
    results = retriever.retrieve("What is the protocol for a Severity 1 incident?", admin_user)
    sop_results = [r for r in results if "Incident Management" in r.document_title]
    assert len(sop_results) == 0


def test_out_of_scope_question_yields_no_results(populated_knowledge_service):
    """Test that questions unrelated to company documentation return empty results."""
    service, admin_user, db_path = populated_knowledge_service
    retriever = TFIDFRetriever(db_path=db_path)
    retriever.build_index()

    results = retriever.retrieve("What is the recipe for chocolate chip cookies?", admin_user)
    assert len(results) == 0
