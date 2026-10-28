# User Guide: Internal Company Knowledge Assistant

This guide provides instructions for setting up, launching, and demonstrating the **Internal Company Knowledge Assistant** on a local Windows workstation.

---

## 1. System Requirements & Prerequisites

- **Operating System:** Windows 10, Windows 11, or Windows Server.
- **Python Version:** Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Network Access:** Not required at runtime. The application runs entirely offline.
- **Hardware:** Standard consumer CPU; 2 GB of available RAM.

---

## 2. Installation Instructions (Windows)

1. **Open PowerShell or Command Prompt** and navigate to the project directory:
   ```powershell
   cd "c:\skips\sem-3\New folder (2)"
   ```

2. **Verify Python Availability:**
   ```powershell
   python --version
   ```

3. **Install Dependencies:**
   ```powershell
   python -m pip install -r requirements.txt
   ```

---

## 3. Launching the Application

Start the Streamlit application using the standard launch command:

```powershell
python -m streamlit run app.py
```

Streamlit will print the local URL in the console:
```text
Local URL: http://localhost:8501
Network URL: http://...
```
Open your web browser (Chrome, Edge, or Firefox) and navigate to `http://localhost:8501`.

---

## 4. Initial Setup & Default Demonstration Accounts

On first launch, the application automatically:
1. Creates the SQLite database at `data/assistant.db`.
2. Seeds initial standard categories and access groups.
3. Automatically sets up the primary Administrator account.
4. Auto-indexes the four included synthetic demonstration documents.

### Preconfigured Demonstration Credentials:

| Role | Username | Password | Access Groups |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `Admin@12345` | All Groups (`All Employees`, `HR`, `Engineering`, `Finance`, `Executive`) |
| **Standard Employee** | `employee_demo` | `Emp@12345` | `All Employees`, `Engineering & IT` |

> [!TIP]
> The login screen features a **"Academic Demonstration Quick-Login"** panel with one-click buttons to instantly log in as either the **Administrator** or **Standard Employee** without typing credentials.

---

## 5. Walkthrough of Main Application Features

### 5.1. Asking Questions (Ask Knowledge Assistant)
1. In the sidebar, select **"🔍 Ask Knowledge Assistant"**.
2. Type an inquiry in natural language into the input box:
   - Example 1: `What are the mandatory core collaboration hours?`
   - Example 2: `What discount applies to a 12-month contract?`
   - Example 3: `What is the protocol for Severity 1 incident escalation?`
3. Click **"🔍 Search Knowledge"**.
4. The system presents:
   - A synthesized **Direct Evidence Summary** highlighting facts and numerical terms.
   - Expandable **Source Citations** detailing the document title, category, physical page number (for PDFs), section heading, relevance score, and the exact supporting excerpt.
   - An optional **"Preview Source Content"** drawer to view full excerpt chunks.

### 5.2. Insufficient Evidence Behavior (Zero Hallucination)
- Test asking an unsupported or unrelated question, such as:  
  `What are the sales quotas for the Tokyo sales division?`
- The assistant displays a yellow notice:  
  **"⚠️ Insufficient Evidence Found"**  
  *No sufficient evidence was found in the approved company documents to answer this question. To prevent misinformation, this assistant does not guess policies, pricing, or procedures.*

### 5.3. Testing Access Isolation (Confidentiality Protection)
1. While logged in as **Standard Employee (`employee_demo`)**, ask:  
   `What is the maximum executive performance incentive bonus pool?`  
   *Result:* The employee receives **"Insufficient Evidence"** because the Executive Compensation document is classified as `Confidential` and restricted to `Executive Leadership`.
2. Sign out and sign in as **Administrator (`admin`)**. Ask the exact same question.  
   *Result:* The Administrator receives the grounded answer citing **Executive Leadership Strategy & Bonus Pool** with the verbatim figure of `$2,500,000`.

### 5.4. Uploading Company Documents
1. In the sidebar, select **"📤 Upload Documents"**.
2. Upload a `.pdf`, `.docx`, or `.txt` file.
3. Enter a title, choose a category, and select an access classification (`Public`, `Restricted`, or `Confidential`).
4. If `Restricted` or `Confidential`, select which groups are authorized to view it.
5. Click **"Upload and Process Document"**.
   - If uploaded by an ordinary employee, it is submitted into **Pending Approval** status.
   - If uploaded by an Administrator, you can check the **"Auto-Approve"** box to index immediately.

### 5.5. Document Review & Approval Workflow (Admin / Reviewer)
1. Select **"⚖️ Document Review"** from the sidebar.
2. In the **"Pending Approval"** tab, inspect all pending submissions and review their extracted text chunks.
3. Choose either:
   - **Approve & Index:** Approves the document and automatically rebuilds the TF-IDF vector index so it becomes immediately searchable.
   - **Reject Document:** Requires a formal rejection reason and prevents the document from ever entering the search index.
4. In the **"Approved Documents Management"** tab, you can click **"Revoke Approval"** on any live document, instantly deactivating it from all employee search queries.

### 5.6. User Management (Admin Only)
1. Select **"👥 User Management"** from the sidebar.
2. View existing users, their roles, and assigned access groups.
3. Register new users with specified roles (`Employee`, `Reviewer`, `Administrator`) and department groups.
4. Modify user roles or toggle account status between `Active` and `Disabled`.

### 5.7. Question History
1. Select **"📜 My Question History"** from the sidebar.
2. Review past questions, timestamps, answers, and verified source counts.
3. Ordinary employees can only see their own history.
4. Click **"Clear My History"** to purge personal records at any time.

### 5.8. System Settings & Index Diagnostics (Admin Only)
1. Select **"⚙️ System Settings"**.
2. Inspect the vector space index health, indexed chunk counts, and vocabulary token volume.
3. Click **"Force Rebuild Retrieval Index"** to trigger an on-demand re-indexing of all approved documents.
4. Create custom document categories on demand.
