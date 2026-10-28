# Automated Test & Quality Assurance Report

**Project:** Internal Company Knowledge Assistant  
**Test Harness:** `pytest` 9.2.0  
**Runtime:** Python 3.14.3 (Windows 64-bit)  
**Execution Timestamp:** 2026-10-28  
**Final Test Status:** 21 Passed, 0 Failed (100% Success Rate)

---

## 1. Test Suite Summary Matrix

| Test Module | Coverage Scope | Tests | Result | Status |
| :--- | :--- | :---: | :---: | :---: |
| [`tests/test_database.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_database.py) | Schema creation, foreign key constraints, idempotent data seeding | 3 | 3 Passed | ✅ SUCCESS |
| [`tests/test_auth_access.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_auth_access.py) | Password hashing (bcrypt), RBAC roles, document access boundaries | 4 | 4 Passed | ✅ SUCCESS |
| [`tests/test_document_processing.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_document_processing.py) | PDF, DOCX, TXT extraction, page tracking, chunking (~500w/75w) | 5 | 5 Passed | ✅ SUCCESS |
| [`tests/test_retriever.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_retriever.py) | TF-IDF ranking, known queries, pending doc exclusion, out-of-scope | 4 | 4 Passed | ✅ SUCCESS |
| [`tests/test_answer_generation.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_answer_generation.py) | Grounded evidence synthesis, citations, insufficient evidence check | 3 | 3 Passed | ✅ SUCCESS |
| [`tests/test_approval_workflow.py`](file:///c:/skips/sem-3/New%20folder%20(2)/tests/test_approval_workflow.py) | Pending -> Approved -> Revoked lifecycle, rejection reason enforce | 2 | 2 Passed | ✅ SUCCESS |
| **Total** | | **21** | **21 Passed** | **100% PASS** |

---

## 2. Granular Test Breakdown & Verifications

### 2.1. Database Integrity & Constraints (`test_database.py`)
- `test_database_initialization`: Validates that all 9 required relational tables (`users`, `access_groups`, `user_groups`, `document_categories`, `documents`, `document_permissions`, `document_chunks`, `question_history`, `document_review_history`) and their indices exist.
- `test_foreign_key_enforcement`: Confirms that `PRAGMA foreign_keys = ON;` is enforced. Inserting child chunks pointing to a nonexistent document ID correctly raises `sqlite3.IntegrityError`.
- `test_seed_initial_data`: Confirms standard categories and groups are initialized and that subsequent seed executions are fully idempotent without throwing primary-key conflicts.

### 2.2. Authentication & Access Control (`test_auth_access.py`)
- `test_password_hashing`: Verifies `bcrypt` cryptographic hashing with unique random salts. Confirms that blank passwords and mismatched inputs evaluate to `False`.
- `test_user_creation_and_authentication`: Verifies user registration, role validation, group assignments, and credential verification.
- `test_rbac_permissions`: Proves that `is_admin`, `can_manage_users`, and `can_review_documents` correctly reflect role boundaries across Administrators, Reviewers, and Employees.
- `test_document_access_isolation`: Proves that an ordinary employee in the Engineering group can access Public and Engineering documents, but is strictly blocked from retrieving or viewing documents restricted to HR or classified as Confidential.

### 2.3. Document Processing & Extraction (`test_document_processing.py`)
- `test_validate_file_upload`: Confirms rejection of unsupported file formats (`.exe`) and empty zero-byte files.
- `test_txt_extraction`: Confirms structured extraction from text files with heading identification and normalization.
- `test_docx_extraction`: Confirms table cells, headers, and paragraphs are extracted from Microsoft Word DOCX files.
- `test_pdf_extraction_page_preservation`: Confirms PyMuPDF extracts text while strictly preserving physical page indices (Page 1 vs. Page 2).
- `test_text_chunking`: Proves that large text blocks are split into overlapping chunks respecting target word thresholds (~500 words, ~75 word overlap) while preserving heading and page metadata.

### 2.4. Retrieval & Indexing Engine (`test_retriever.py`)
- `test_retrieval_accuracy_known_question`: Verifies that a natural language query regarding core hours accurately ranks the FAQ document at the top with a similarity score > 0.15.
- `test_retrieval_pricing_question`: Verifies that contract discount inquiries accurately retrieve the DOCX pricing document.
- `test_pending_document_is_not_retrieved`: Proves that documents in `Pending Approval` status are completely excluded from search results.
- `test_out_of_scope_question_yields_no_results`: Proves that unrelated questions (e.g., cookie recipes) return 0 results.

### 2.5. Grounded Answering & Citations (`test_answer_generation.py`)
- `test_grounded_answer_generation`: Verifies that answers return `status == 'answered'` with verified citations citing document titles and page/section numbers.
- `test_insufficient_evidence_behavior`: Proves that when substantive keywords do not match the company documentation, the assistant returns `status == 'insufficient_evidence'` with an explicit disclaimer.
- `test_confidential_document_isolation`: Demonstrates that when an employee asks about executive compensation, the assistant returns `insufficient_evidence` with 0 citations, while an administrator receives the grounded answer.

### 2.6. Document Approval Lifecycle (`test_approval_workflow.py`)
- `test_complete_approval_workflow`: Validates the complete lifecycle: an employee upload starts in `Pending Approval` (unsearchable), an unauthorized approval attempt fails, reviewer approval makes it searchable, and revoking approval immediately deactivates it from search results.
- `test_rejection_workflow`: Confirms that rejecting a document requires a mandatory reason and keeps it unsearchable.

---

## 3. Test Execution Command & Verification Log

```powershell
python -m pytest tests/ -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\viraj\AppData\Local\Programs\Python\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\skips\sem-3\New folder (2)
collecting ... collected 21 items

tests/test_answer_generation.py::test_grounded_answer_generation PASSED  [  4%]
tests/test_answer_generation.py::test_insufficient_evidence_behavior PASSED [  9%]
tests/test_answer_generation.py::test_confidential_document_isolation PASSED [ 14%]
tests/test_approval_workflow.py::test_complete_approval_workflow PASSED  [ 19%]
tests/test_approval_workflow.py::test_rejection_workflow PASSED          [ 23%]
tests/test_auth_access.py::test_password_hashing PASSED                  [ 28%]
tests/test_auth_access.py::test_user_creation_and_authentication PASSED  [ 33%]
tests/test_auth_access.py::test_rbac_permissions PASSED                  [ 38%]
tests/test_auth_access.py::test_document_access_isolation PASSED         [ 42%]
tests/test_database.py::test_database_initialization PASSED              [ 47%]
tests/test_database.py::test_foreign_key_enforcement PASSED              [ 52%]
tests/test_database.py::test_seed_initial_data PASSED                    [ 57%]
tests/test_document_processing.py::test_validate_file_upload PASSED      [ 61%]
tests/test_document_processing.py::test_txt_extraction PASSED            [ 66%]
tests/test_document_processing.py::test_docx_extraction PASSED           [ 71%]
tests/test_document_processing.py::test_pdf_extraction_page_preservation PASSED [ 76%]
tests/test_document_processing.py::test_text_chunking PASSED             [ 80%]
tests/test_retriever.py::test_retrieval_accuracy_known_question PASSED   [ 85%]
tests/test_retriever.py::test_retrieval_pricing_question PASSED          [ 90%]
tests/test_retriever.py::test_pending_document_is_not_retrieved PASSED   [ 95%]
tests/test_retriever.py::test_out_of_scope_question_yields_no_results PASSED [100%]

====================== 21 passed, 14 warnings in 16.41s =======================
```
