"""Utility script to generate realistic non-confidential sample demonstration documents

in PDF, DOCX, and TXT formats for Internal Company Knowledge Assistant.
"""

from pathlib import Path
import docx
import fitz

SAMPLE_DIR = Path(__file__).resolve().parent / "data" / "sample_documents"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def create_txt_faq() -> Path:
    """Create a sample FAQ text document."""
    content = """# Company Remote Work and Core Hours Policy FAQ

## Overview
This document answers frequently asked questions regarding the company's hybrid workplace framework, flexible hours, and core collaboration periods.

## Question 1: What are the mandatory core collaboration hours?
All full-time employees are required to be online and available for synchronous collaboration during the core window of 10:00 AM to 3:00 PM local time. Flexible schedule adjustments outside these core hours must be pre-approved by the department manager.

## Question 2: What is the home office technology stipend?
Full-time regular employees are eligible for a one-time home office setup stipend of $500 upon completing 90 days of continuous employment. In addition, an internet connectivity reimbursement of $50 per month is provided on submitting monthly expense proofs.

## Question 3: How is annual leave requested and approved?
Employees must submit planned paid time off (PTO) requests through the HR portal at least 14 calendar days in advance for leaves exceeding 3 consecutive business days. Emergency personal leave must be reported to the team supervisor before 9:00 AM on the day of absence.

## Question 4: What is the equipment return policy upon departure?
All company-issued hardware, including laptops, monitors, security tokens, and access badges, must be returned to the IT Asset Management desk within 5 business days following an employee's final working day.
"""
    path = SAMPLE_DIR / "FAQ_Remote_Work_and_Leave.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    return path


def create_docx_pricing() -> Path:
    """Create a sample DOCX document covering Service Descriptions and Pricing Rules."""
    doc = docx.Document()
    doc.add_heading("Cloud Infrastructure Services & Pricing Rules", level=1)

    doc.add_heading("Service Overview", level=2)
    doc.add_paragraph(
        "Apex Enterprise Cloud provides managed Kubernetes clusters, dedicated database hosting, "
        "and distributed object storage designed for mission-critical corporate workloads. "
        "Our standard production tier guarantees 99.95% uptime backed by financial service level credits."
    )

    doc.add_heading("Tiered Pricing Structure", level=2)
    doc.add_paragraph(
        "Pricing is billed monthly based on allocated computing instances and storage volume:"
    )

    # Add pricing table
    table = doc.add_table(rows=1, cols=4)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Tier Level"
    hdr_cells[1].text = "Virtual CPUs / RAM"
    hdr_cells[2].text = "Monthly Base Fee"
    hdr_cells[3].text = "Over-quota Rate"

    data = [
        ("Starter Tier", "2 vCPU / 4 GB RAM", "$120 / month", "$0.05 per GB-hour"),
        ("Standard Production", "8 vCPU / 32 GB RAM", "$480 / month", "$0.04 per GB-hour"),
        ("High-Performance Tier", "32 vCPU / 128 GB RAM", "$1,450 / month", "$0.03 per GB-hour"),
    ]

    for tier, specs, fee, overquota in data:
        row_cells = table.add_row().cells
        row_cells[0].text = tier
        row_cells[1].text = specs
        row_cells[2].text = fee
        row_cells[3].text = overquota

    doc.add_heading("Volume Discount Policy and Exceptions", level=2)
    doc.add_paragraph(
        "Clients committing to a minimum 12-month annual contract receive a 15% discount on monthly base fees. "
        "Clients committing to 36-month contracts receive a 25% discount. "
        "Discounts cannot be combined with educational or non-profit waivers. "
        "Any custom pricing exception exceeding 30% discount requires explicit written authorization from the Chief Commercial Officer (CCO)."
    )

    doc.add_heading("Service Level Agreement (SLA) Penalties", level=2)
    doc.add_paragraph(
        "If monthly availability drops between 99.0% and 99.94%, a 10% billing credit is credited to the next invoice. "
        "If monthly availability drops below 99.0%, a 25% billing credit applies. "
        "Customers must claim SLA penalties in writing within 30 days of the affected calendar month."
    )

    path = SAMPLE_DIR / "Service_Cloud_Hosting_Pricing_Rules.docx"
    doc.save(str(path))
    return path


def create_pdf_sop() -> Path:
    """Create a multi-page PDF document for Standard Operating Procedures using PyMuPDF."""
    doc = fitz.open()

    # Page 1: Title and Severity Classifications
    page1 = doc.new_page(width=595, height=842)
    text1 = """IT Incident Management Standard Operating Procedure (SOP)
Document Code: SOP-IT-2026-04 | Classification: Public | Version: 2.1

1. Purpose and Scope
This Standard Operating Procedure establishes the incident response lifecycle for all production IT services, customer portals, and internal networks operated by the company. All on-call engineers, support leads, and system administrators must adhere to these steps.

2. Incident Severity Classification Matrix
Incidents are categorized into three operational severity levels:

- Severity 1 (Critical): Total outage of customer-facing services, data loss vulnerability, or complete payroll system failure. Target acknowledgment time is within 15 minutes. Escalation to Incident Commander is mandatory.
- Severity 2 (Major): Degradation of core systems affecting more than 20% of users, high-latency database queries, or failure of redundant payment gateways. Target acknowledgment time is within 45 minutes.
- Severity 3 (Minor): Individual employee desktop issues, internal wiki glitches, or non-blocking report generation errors. Target resolution window is 2 business days.

3. Escalation Protocols
When a Severity 1 incident is confirmed, the on-duty engineer must immediately initiate the incident bridge call and notify the Executive On-Call channel via the emergency pager system."""

    page1.insert_text(fitz.Point(50, 60), text1, fontsize=10, fontname="helv")

    # Page 2: Root Cause Analysis and Post-Mortem Requirements
    page2 = doc.new_page(width=595, height=842)
    text2 = """IT Incident Management SOP - Page 2

4. Communication Cadence During Major Outages
During active Severity 1 incidents, status updates must be published to the public status page and internal announcement channel at intervals not exceeding 30 minutes, even if no technical progress has occurred.

5. Post-Incident Review and Blameless Post-Mortem
A blameless post-mortem meeting must be conducted within 72 hours of resolving any Severity 1 or recurring Severity 2 incident. 

Key deliverables required for the post-mortem report include:
- A complete timestamped incident timeline detailing detection, mitigation, and resolution steps.
- Identification of root technical triggers and contributing architectural vulnerabilities.
- Action items with named owners and target completion dates not to exceed 14 business days.
- Sign-off from both the Technical Operations Director and the Product Engineering Lead.

6. Archival and Audit Compliance
All incident bridge audio recordings, chat logs, and post-mortem documents must be archived in the security vault for a minimum retention period of 3 years to satisfy ISO 27001 audit standards."""

    page2.insert_text(fitz.Point(50, 60), text2, fontsize=10, fontname="helv")

    path = SAMPLE_DIR / "SOP_IT_Incident_Management.pdf"
    doc.save(str(path))
    doc.close()
    return path


def create_confidential_doc() -> Path:
    """Create a sample Confidential document restricted to Executive Leadership."""
    content = """# CONFIDENTIAL: Executive Leadership Committee & Board Minutes

Classification: Confidential (Executive Leadership Only)
Document Identifier: EXEC-CONF-2026-Q1

## Strategic Mergers & Executive Compensation Structure
This document contains highly sensitive corporate strategy and executive compensation targets. 
Strictly restricted to Board Members and C-Suite Executives (grp_exec).

### Executive Bonus Criteria for 2026
Executive annual performance bonuses are contingent upon achieving a 22% year-over-year revenue growth and maintaining an employee retention score above 88%. The maximum performance incentive pool is capped at $2,500,000 across all executive officers.

### Project Horizon Acquisition Target
The Board has formally authorized due diligence into the proposed acquisition of Project Horizon for an enterprise valuation between $14,000,000 and $16,500,000. All details are protected under NDA-774.
"""
    path = SAMPLE_DIR / "CONFIDENTIAL_Executive_Compensation_2026.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    return path


if __name__ == "__main__":
    p1 = create_txt_faq()
    p2 = create_docx_pricing()
    p3 = create_pdf_sop()
    p4 = create_confidential_doc()
    print(f"Generated sample documents:\n- {p1}\n- {p2}\n- {p3}\n- {p4}")
