"""Unit tests for document processing, text extraction, validation, and chunking."""

from pathlib import Path
import pytest

from backend.document_processor import (
    compute_file_hash,
    extract_document,
    extract_from_pdf,
    extract_from_docx,
    extract_from_txt,
    validate_file_upload,
)
from backend.text_chunker import (
    chunk_document_sections,
    chunk_section,
    ExtractedSection,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_documents"


def test_validate_file_upload():
    """Verify file validation rejects unsupported extensions and empty payloads."""
    valid, err, ext = validate_file_upload("test.pdf", b"%PDF-1.4 sample content")
    assert valid is True
    assert ext == ".pdf"

    valid, err, ext = validate_file_upload("malicious.exe", b"binary code")
    assert valid is False
    assert "Unsupported file format" in err

    valid, err, ext = validate_file_upload("empty.txt", b"")
    assert valid is False
    assert "empty" in err.lower() or "0 bytes" in err.lower()


def test_txt_extraction():
    """Test extracting text and structured sections from sample FAQ text document."""
    txt_path = SAMPLE_DIR / "FAQ_Remote_Work_and_Leave.txt"
    assert txt_path.exists(), "Sample FAQ text document must exist."

    with open(txt_path, "rb") as f:
        content = f.read()

    res = extract_document("FAQ_Remote_Work_and_Leave.txt", content)
    assert res.success is True
    assert res.file_type == "txt"
    assert res.total_words > 50
    assert len(res.sections) >= 3
    assert any("core collaboration" in s.text.lower() for s in res.sections)


def test_docx_extraction():
    """Test extracting text and table data from sample DOCX document."""
    docx_path = SAMPLE_DIR / "Service_Cloud_Hosting_Pricing_Rules.docx"
    assert docx_path.exists(), "Sample DOCX document must exist."

    with open(docx_path, "rb") as f:
        content = f.read()

    res = extract_document("Service_Cloud_Hosting_Pricing_Rules.docx", content)
    assert res.success is True
    assert res.file_type == "docx"
    assert res.total_words > 50
    # Check that pricing tables and clauses are extracted
    raw_lower = res.raw_text.lower()
    assert "starter tier" in raw_lower
    assert "$120" in raw_lower or "120" in raw_lower
    assert "discount" in raw_lower


def test_pdf_extraction_page_preservation():
    """Test extracting text and preserving page numbers from sample multi-page PDF."""
    pdf_path = SAMPLE_DIR / "SOP_IT_Incident_Management.pdf"
    assert pdf_path.exists(), "Sample PDF document must exist."

    with open(pdf_path, "rb") as f:
        content = f.read()

    res = extract_document("SOP_IT_Incident_Management.pdf", content)
    assert res.success is True
    assert res.file_type == "pdf"
    assert res.total_pages_or_sections == 2
    assert len(res.sections) == 2

    # Check page numbers
    assert res.sections[0].page_number == 1
    assert "Severity 1" in res.sections[0].text

    assert res.sections[1].page_number == 2
    assert "Post-Mortem" in res.sections[1].text or "post-mortem" in res.sections[1].text.lower()


def test_text_chunking():
    """Test that text chunking splits large text while preserving headings and page numbers."""
    # Create a synthetic large section with 1200 words
    words = [f"word{i}" for i in range(1200)]
    long_text = "\n\n".join([" ".join(words[i : i + 100]) for i in range(0, 1200, 100)])

    sec = ExtractedSection(
        page_number=3,
        section_heading="Large Policy Section",
        text=long_text,
    )

    chunks = chunk_section(
        section=sec,
        document_id="doc_test_123",
        starting_index=0,
        target_words=500,
        overlap_words=75,
    )

    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "doc_test_123"
        assert c.page_number == 3
        assert c.section_heading == "Large Policy Section"
        assert c.word_count <= 600  # Within target tolerance
