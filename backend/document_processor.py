"""Document processing and text extraction module for Internal Company Knowledge Assistant.

Extracts text and structural metadata from PDF (PyMuPDF), DOCX (python-docx), and TXT files,
validating file integrity, detecting duplicates via SHA-256 cryptographic hashes,
and producing structured page- and section-aware text records.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# PyMuPDF
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# python-docx
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# Maximum upload limit: 25 MB
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@dataclass
class ExtractedSection:
    """Represents a discrete structural unit (page or section) extracted from a document."""
    page_number: Optional[int]
    section_heading: Optional[str]
    text: str
    word_count: int = 0

    def __post_init__(self) -> None:
        self.text = normalize_whitespace(self.text)
        self.word_count = len(self.text.split()) if self.text else 0


@dataclass
class ExtractionResult:
    """Complete result of document extraction."""
    success: bool
    error_message: Optional[str] = None
    file_type: str = ""
    file_hash: str = ""
    file_size: int = 0
    total_pages_or_sections: int = 0
    total_words: int = 0
    sections: List[ExtractedSection] = field(default_factory=list)
    raw_text: str = ""
    is_scanned_pdf: bool = False


def compute_file_hash(content_bytes: bytes) -> str:
    """Compute SHA-256 cryptographic hash of byte content."""
    hasher = hashlib.sha256()
    hasher.update(content_bytes)
    return hasher.hexdigest()


def normalize_whitespace(text: str) -> str:
    """Clean and normalize whitespace while preserving numbers, prices, and punctuation.

    Removes excessive empty lines, replaces non-breaking spaces, and standardizes spacing.
    """
    if not text:
        return ""
    # Replace non-breaking spaces and unusual unicode spaces
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    # Replace 3 or more newlines with two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Replace multiple inline whitespace (tabs/spaces) with a single space
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def validate_file_upload(
    filename: str,
    content_bytes: bytes,
) -> Tuple[bool, Optional[str], str]:
    """Validate file extension and size.

    Args:
        filename: Original file name.
        content_bytes: Uploaded byte content.

    Returns:
        Tuple[bool, Optional[str], str]: (is_valid, error_msg, normalized_extension)
    """
    if not filename or not content_bytes:
        return False, "File name or content is empty.", ""

    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return (
            False,
            f"Unsupported file format '{ext}'. Supported formats are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
            ext,
        )

    if len(content_bytes) > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return (
            False,
            f"File size exceeds maximum permitted limit of {max_mb} MB.",
            ext,
        )

    if len(content_bytes) == 0:
        return False, "Uploaded file contains 0 bytes.", ext

    return True, None, ext


def extract_from_pdf(content_bytes: bytes) -> ExtractionResult:
    """Extract structured text from PDF byte content using PyMuPDF."""
    if not HAS_PYMUPDF:
        return ExtractionResult(
            success=False,
            error_message="PyMuPDF library is not available in the environment.",
            file_type="pdf",
        )

    sections: List[ExtractedSection] = []
    total_words = 0
    full_text_parts: List[str] = []

    try:
        # Open PDF from memory stream
        doc = fitz.open(stream=content_bytes, filetype="pdf")
        page_count = len(doc)

        if page_count == 0:
            return ExtractionResult(
                success=False,
                error_message="PDF contains no pages.",
                file_type="pdf",
                total_pages_or_sections=0,
            )

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_num = page_idx + 1
            page_text = page.get_text("text") or ""
            cleaned_text = normalize_whitespace(page_text)

            if cleaned_text:
                # Attempt to detect heading from first line if short and title-like
                first_line = cleaned_text.split("\n")[0].strip()
                heading = first_line if len(first_line) < 100 and not first_line.endswith(".") else f"Page {page_num}"

                sec = ExtractedSection(
                    page_number=page_num,
                    section_heading=heading,
                    text=cleaned_text,
                )
                sections.append(sec)
                total_words += sec.word_count
                full_text_parts.append(cleaned_text)

        doc.close()

        # Check for scanned PDF condition (pages exist but 0 extractable text)
        if page_count > 0 and total_words == 0:
            return ExtractionResult(
                success=False,
                error_message=(
                    "PDF appears to be scanned or contains only raster images with no extractable text. "
                    "An Optical Character Recognition (OCR) enhancement is required for scanned documents."
                ),
                file_type="pdf",
                total_pages_or_sections=page_count,
                total_words=0,
                is_scanned_pdf=True,
            )

        return ExtractionResult(
            success=True,
            file_type="pdf",
            total_pages_or_sections=page_count,
            total_words=total_words,
            sections=sections,
            raw_text="\n\n".join(full_text_parts),
        )

    except Exception as exc:
        return ExtractionResult(
            success=False,
            error_message=f"Failed to process PDF document: {str(exc)}",
            file_type="pdf",
        )


def extract_from_docx(content_bytes: bytes) -> ExtractionResult:
    """Extract structured text from DOCX byte content using python-docx."""
    if not HAS_DOCX:
        return ExtractionResult(
            success=False,
            error_message="python-docx library is not available in the environment.",
            file_type="docx",
        )

    import io

    try:
        doc = docx.Document(io.BytesIO(content_bytes))
        sections: List[ExtractedSection] = []
        current_heading = "General"
        current_paras: List[str] = []
        section_idx = 1
        total_words = 0

        def flush_section() -> None:
            nonlocal current_paras, current_heading, section_idx, total_words
            if current_paras:
                sec_text = normalize_whitespace("\n\n".join(current_paras))
                if sec_text:
                    sec = ExtractedSection(
                        page_number=None,  # DOCX lacks reliable physical pagination
                        section_heading=current_heading,
                        text=sec_text,
                    )
                    sections.append(sec)
                    total_words += sec.word_count
                    section_idx += 1
                current_paras = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            style_name = (p.style.name if p.style else "").lower()
            if "heading" in style_name or "title" in style_name:
                flush_section()
                current_heading = text
            else:
                current_paras.append(text)

        # Include tables if any
        for table in doc.tables:
            table_rows: List[str] = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                if any(row_cells):
                    table_rows.append(" | ".join(row_cells))
            if table_rows:
                current_paras.append("\n".join(table_rows))

        flush_section()

        if total_words == 0:
            return ExtractionResult(
                success=False,
                error_message="DOCX document contains no readable text or paragraphs.",
                file_type="docx",
                total_pages_or_sections=0,
                total_words=0,
            )

        full_raw = "\n\n".join(s.text for s in sections)
        return ExtractionResult(
            success=True,
            file_type="docx",
            total_pages_or_sections=len(sections),
            total_words=total_words,
            sections=sections,
            raw_text=full_raw,
        )

    except Exception as exc:
        return ExtractionResult(
            success=False,
            error_message=f"Failed to process DOCX document: {str(exc)}",
            file_type="docx",
        )


def extract_from_txt(content_bytes: bytes) -> ExtractionResult:
    """Extract structured text from TXT byte content with encoding fallback."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    decoded_text = None

    for enc in encodings:
        try:
            decoded_text = content_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        return ExtractionResult(
            success=False,
            error_message="Could not decode text file with standard encodings (UTF-8, Latin-1, CP1252).",
            file_type="txt",
        )

    cleaned_text = normalize_whitespace(decoded_text)
    if not cleaned_text:
        return ExtractionResult(
            success=False,
            error_message="Text document is empty.",
            file_type="txt",
            total_pages_or_sections=0,
            total_words=0,
        )

    # Break into logical sections by Markdown-style headings '# ' or double blank lines
    blocks = re.split(r"\n(?=[#=]{1,3}\s|[A-Z0-9\s]{3,30}:|\n\n)", cleaned_text)
    sections: List[ExtractedSection] = []
    total_words = 0

    for i, block in enumerate(blocks, start=1):
        block_clean = normalize_whitespace(block)
        if not block_clean:
            continue
        first_line = block_clean.split("\n")[0].strip()
        heading = re.sub(r"^[#=\-\*\s]+", "", first_line).strip()
        if len(heading) > 80:
            heading = f"Section {i}"

        sec = ExtractedSection(
            page_number=None,
            section_heading=heading,
            text=block_clean,
        )
        sections.append(sec)
        total_words += sec.word_count

    if not sections:
        sec = ExtractedSection(page_number=None, section_heading="General", text=cleaned_text)
        sections.append(sec)
        total_words = sec.word_count

    return ExtractionResult(
        success=True,
        file_type="txt",
        total_pages_or_sections=len(sections),
        total_words=total_words,
        sections=sections,
        raw_text=cleaned_text,
    )


def extract_document(
    filename: str,
    content_bytes: bytes,
) -> ExtractionResult:
    """Entry point for document validation, hashing, and extraction.

    Args:
        filename: Original file name.
        content_bytes: Uploaded byte content.

    Returns:
        ExtractionResult: Extraction outcome with metadata and structured sections.
    """
    is_valid, err_msg, ext = validate_file_upload(filename, content_bytes)
    if not is_valid:
        return ExtractionResult(
            success=False,
            error_message=err_msg,
            file_type=ext.lstrip("."),
            file_size=len(content_bytes) if content_bytes else 0,
        )

    file_hash = compute_file_hash(content_bytes)
    file_size = len(content_bytes)

    if ext == ".pdf":
        res = extract_from_pdf(content_bytes)
    elif ext == ".docx":
        res = extract_from_docx(content_bytes)
    elif ext == ".txt":
        res = extract_from_txt(content_bytes)
    else:
        return ExtractionResult(
            success=False,
            error_message=f"Unsupported format: {ext}",
            file_type=ext.lstrip("."),
            file_hash=file_hash,
            file_size=file_size,
        )

    res.file_hash = file_hash
    res.file_size = file_size
    return res


def save_uploaded_file(
    content_bytes: bytes,
    original_filename: str,
    upload_dir: Optional[Path] = None,
) -> Tuple[str, Path]:
    """Store uploaded document securely with a random internal filename to prevent path traversal.

    Returns:
        Tuple[str, Path]: (internal_file_id, full_saved_path)
    """
    if upload_dir is None:
        upload_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(original_filename).suffix.lower()
    internal_id = f"doc_{uuid.uuid4().hex}"
    safe_filename = f"{internal_id}{ext}"
    full_path = upload_dir / safe_filename

    with open(full_path, "wb") as f:
        f.write(content_bytes)

    return internal_id, full_path
