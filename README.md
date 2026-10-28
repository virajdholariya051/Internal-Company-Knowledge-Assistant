# Internal Company Knowledge Assistant

An honest, evidence-grounded, and secure knowledge retrieval web application built for an **M.Sc. Information Technology** academic project.

The application enables employees to search internal company documents (SOPs, FAQs, pricing rules, service descriptions, and policies) using natural language, retrieving relevant passages with verifiable page-level and section-level citations while strictly declining to answer when evidence is unavailable.

---

## 🌟 Key Highlights

- **100% Local & Cost-Free:** Operates completely offline on Windows without requiring paid external APIs, proprietary models, or cloud subscriptions.
- **Zero-Hallucination Policy:** If approved company documents do not contain sufficient evidence to answer an inquiry, the system explicitly reports that no answer was found rather than guessing.
- **Verifiable Citations:** Every response includes exact source citations pointing to document titles, physical page numbers (for PDFs), section headings, and supporting excerpts.
- **Role-Based Access Control (RBAC):** Supports `Administrator`, `Reviewer`, and `Employee` roles with fine-grained document classification (`Public`, `Restricted`, `Confidential`). Pre-retrieval security ensures employees can never search or cite documents restricted to other departments.
- **Document Approval Workflow:** Newly uploaded documents begin in `Pending Approval`. Only approved documents are indexed for search. Administrators and reviewers can approve or reject with mandatory cause, or revoke prior approvals.
- **Cryptographic Integrity:** Files are validated using SHA-256 cryptographic hashes to prevent duplicate ingestion, and stored using safe internal identifiers to eliminate path traversal vulnerabilities.
- **Multi-Format Ingestion:** Extracts text from PDF (PyMuPDF), DOCX (python-docx), and plain text files with automatic encoding fallbacks.

---

## 🏗️ Technology Stack

- **User Interface:** [Streamlit](https://streamlit.io/)
- **Core Language:** Python 3.10+ (tested on Python 3.14 on Windows)
- **Database & Metadata:** SQLite 3 (with `PRAGMA foreign_keys = ON;`)
- **Document Extraction:** PyMuPDF (`fitz`), `python-docx`
- **Retrieval Engine:** scikit-learn (TF-IDF Vectorizer with unigram/bigram tokens & cosine similarity)
- **Security & Hashing:** `bcrypt` (with PBKDF2-HMAC-SHA256 standard library fallback)
- **Automated Testing:** `pytest` (21 automated tests, 100% pass rate)

---

## 🚀 Quick Start (Windows)

### 1. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. Launch Application
```powershell
python -m streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 3. Run Automated Tests
```powershell
python -m pytest tests/ -v
```

---

## 👥 Demonstration Accounts

On initial launch, the system automatically initializes the database and populates four sample demonstration documents across PDF, DOCX, and TXT formats.

You can use the one-click **"Academic Demonstration Quick-Login"** on the login screen or enter the credentials below:

| Role | Username | Password | Access Description |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `Admin@12345` | Full administrative access, review documents, manage users, rebuild index |
| **Standard Employee** | `employee_demo` | `Emp@12345` | Search authorized public & engineering documents, view personal history |

---

## 📁 Project Directory Structure

```text
internal_company_knowledge_assistant/
│
├── app.py                            # Main Streamlit web application & page router
├── requirements.txt                  # Python dependencies
├── README.md                         # Project overview and quick start
├── .gitignore                        # Git ignore specifications
├── create_sample_docs.py             # Script to regenerate synthetic demo documents
│
├── backend/                          # Decoupled core backend modules
│   ├── __init__.py
│   ├── database.py                   # SQLite schema, connections, and migrations
│   ├── authentication.py             # User accounts, password hashing (bcrypt), login
│   ├── access_control.py             # RBAC and document classification enforcement
│   ├── document_processor.py         # Multi-format extraction (PDF, DOCX, TXT)
│   ├── text_chunker.py               # Context-aware text chunking (~500w / 75w overlap)
│   ├── retriever.py                  # TF-IDF vector space and cosine similarity engine
│   ├── answer_generator.py           # Grounded evidence synthesis & no-answer checks
│   ├── citation_service.py           # Citation generation & excerpt extraction
│   └── knowledge_service.py          # High-level business logic orchestrator
│
├── frontend/                         # Presentation styling
│   ├── __init__.py
│   └── styles.py                     # Custom CSS, badges, and layout components
│
├── data/                             # Application persistence
│   ├── assistant.db                  # Local SQLite database
│   ├── uploads/                      # Safely stored uploaded documents
│   └── sample_documents/             # Synthetic SOP, FAQ, Pricing, and Confidential docs
│
├── tests/                            # Automated test suite (pytest)
│   ├── __init__.py
│   ├── test_database.py              # Schema integrity and foreign keys
│   ├── test_auth_access.py           # Authentication, RBAC, access boundaries
│   ├── test_document_processing.py   # PDF, DOCX, TXT parsing, page preservation
│   ├── test_retriever.py             # TF-IDF search accuracy, pending doc exclusion
│   ├── test_answer_generation.py     # Grounded answers and insufficient evidence checks
│   └── test_approval_workflow.py     # Document approval, rejection, and revocation
│
├── docs/                             # Academic & technical documentation
│   ├── PROJECT_OVERVIEW.md           # Architecture, system design, and ER diagram
│   ├── USER_GUIDE.md                 # Step-by-step user and administration guide
│   ├── TEST_REPORT.md                # QA report and test verification log
│   └── SECURITY_LIMITATIONS.md       # Threat mitigations and operational boundaries
│
└── .agent/                           # Memory, context, and task tracker
    ├── MEMORY.md
    ├── CONTEXT.md
    └── TASKS.md
```

---

## 📚 Academic Documentation Links

For comprehensive evaluation and viva voce defense:
- [Project Architecture & System Design](file:///c:/skips/sem-3/New%20folder%20(2)/docs/PROJECT_OVERVIEW.md)
- [User Guide & Role Walkthroughs](file:///c:/skips/sem-3/New%20folder%20(2)/docs/USER_GUIDE.md)
- [Quality Assurance & Automated Test Report](file:///c:/skips/sem-3/New%20folder%20(2)/docs/TEST_REPORT.md)
- [Security Mitigations & Architectural Boundaries](file:///c:/skips/sem-3/New%20folder%20(2)/docs/SECURITY_LIMITATIONS.md)
