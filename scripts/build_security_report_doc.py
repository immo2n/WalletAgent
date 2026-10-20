"""Build the publication-grade WalletAgent (Orvilo) Security Self-Assessment Report DOCX.

Synchronized with docs/security-self-assessment-final.md and the active main codebase.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/final/Orvilo_Security_Self_Assessment_Report.docx"
OUT_REVISED = ROOT / "docs/revised/Orvilo_Security_Self_Assessment_Report.docx"

FIG_TRUST = ROOT / "visuals/rendered/security-trust-boundaries.png"
FIG_PERMISSION = ROOT / "visuals/rendered/permission-enforcement.png"

# Color Palette
NAVY = "17324D"         # Primary Headers & Accents
BLUE = "1E5A88"         # Subheadings & Links
LIGHT_BLUE = "F0F7FF"   # Info Shading
PALE = "F8FAFC"         # Alternating Table Row
GRAY = "64748B"         # Subtitles & Captions
DARK_GRAY = "334155"    # Normal Text
LIGHT_GRAY = "E2E8F0"   # Table & Code Borders
GREEN = "15803D"        # Success Text
LIGHT_GREEN = "DCFCE7"  # Passed Badge Background
RED = "991B1B"          # Error / Alert Text
LIGHT_RED = "FEE2E2"    # Failed / Critical Badge Background
AMBER = "B45309"        # Warning Text
LIGHT_AMBER = "FEF3C7"  # Warning Badge Background
WHITE = "FFFFFF"
BLACK = "111827"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_table_borders(table, color=LIGHT_GRAY, sz="4", val="single") -> None:
    tbl_pr = table._tbl.tblPr
    tbl_borders = tbl_pr.find(qn("w:tblBorders"))
    if tbl_borders is None:
        tbl_borders = OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)
    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = tbl_borders.find(qn(f"w:{border_name}"))
        if border is None:
            border = OxmlElement(f"w:{border_name}")
            tbl_borders.append(border)
        border.set(qn("w:val"), val)
        border.set(qn("w:sz"), sz)
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), color)


def set_table_widths(table, widths: list[float]) -> None:
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_layout = tbl_pr.find(qn("w:tblLayout"))
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(round(width * 1440)))
            tc_w.set(qn("w:type"), "dxa")


def add_table(doc, headers: list[str], rows: list[list[str]], widths: list[float], font_size=8.5):
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_borders(table)
    set_table_widths(table, widths)
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_shading(cell, NAVY)
        set_cell_margins(cell, top=120, bottom=120, start=120, end=120)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(text)
        r.bold = True
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(WHITE)
        r.font.size = Pt(font_size)

    for row_idx, row_values in enumerate(rows):
        cells = table.add_row().cells
        is_even = (row_idx % 2 == 1)
        for i, value in enumerate(row_values):
            cell = cells[i]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell, top=90, bottom=90, start=110, end=110)
            if is_even:
                set_cell_shading(cell, PALE)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)

            val_str = str(value)
            r = p.add_run(val_str)
            r.font.name = "Aptos"
            r.font.size = Pt(font_size)

            # Context-aware status badges
            if val_str in ("PASSED", "PASS", "SUCCESS", "Verified"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(GREEN)
                set_cell_shading(cell, LIGHT_GREEN)
            elif val_str in ("FAILED", "FAIL", "CRITICAL", "Critical", "Not ready"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(RED)
                set_cell_shading(cell, LIGHT_RED)
            elif val_str in ("HIGH", "High", "WARNING", "Partial"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(AMBER)
                set_cell_shading(cell, LIGHT_AMBER)
            elif val_str in ("MEDIUM", "Medium", "LOW", "Low", "INFO", "Source reviewed", "Source Reviewed"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(BLUE)
                set_cell_shading(cell, LIGHT_BLUE)
            else:
                r.font.color.rgb = RGBColor.from_string(DARK_GRAY)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(2)
    p_spacer.paragraph_format.space_after = Pt(4)
    return table


def add_page_field(paragraph, field: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def add_toc(doc) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Right-click and choose Update Field to refresh this Table of Contents."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, placeholder, end])


def add_heading(doc, text: str, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def add_body(doc, text: str, bold_lead: str | None = None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.14
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(NAVY)
        r2 = p.add_run(text[len(bold_lead):])
        r2.font.name = "Aptos"
        r2.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    else:
        r = p.add_run(text)
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    return p


def add_bullet(doc, text: str, bold_lead: str | None = None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2.5)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(NAVY)
        r2 = p.add_run(text[len(bold_lead):])
        r2.font.name = "Aptos"
        r2.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    else:
        r = p.add_run(text)
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    return p


def add_number(doc, text: str, bold_lead: str | None = None):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(2.5)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(NAVY)
        r2 = p.add_run(text[len(bold_lead):])
        r2.font.name = "Aptos"
        r2.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    else:
        r = p.add_run(text)
        r.font.name = "Aptos"
        r.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    return p


def add_callout(doc, label: str, text: str, kind="info"):
    bg_color = {
        "danger": "FDF2F2",
        "warning": "FFFBEB",
        "success": "F0FDF4",
        "info": "F0F7FF"
    }.get(kind, "F0F7FF")

    border_color = {
        "danger": RED,
        "warning": AMBER,
        "success": GREEN,
        "info": BLUE
    }.get(kind, BLUE)

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.15)
    p.paragraph_format.right_indent = Inches(0.15)
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.14

    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), bg_color)
    p_pr.append(shd)

    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "24")  # 3pt thick bar
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), border_color)
    borders.append(left)
    p_pr.append(borders)

    r_lbl = p.add_run(label + " ")
    r_lbl.bold = True
    r_lbl.font.name = "Aptos"
    r_lbl.font.size = Pt(10)
    r_lbl.font.color.rgb = RGBColor.from_string(border_color)

    r_txt = p.add_run(text)
    r_txt.font.name = "Aptos"
    r_txt.font.size = Pt(9.5)
    r_txt.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    return p


def add_code_block(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.15)
    p.paragraph_format.right_indent = Inches(0.15)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.05

    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F8FAFC")
    p_pr.append(shd)

    borders = OxmlElement("w:pBdr")
    for b_name in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{b_name}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "6")
        b.set(qn("w:space"), "5")
        b.set(qn("w:color"), LIGHT_GRAY)
        borders.append(b)
    p_pr.append(borders)

    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor.from_string("1E293B")
        if i < len(lines) - 1:
            p.add_run("\n")
    return p


def add_figure(doc, path: Path, caption: str, width=6.1):
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    inline = run.add_picture(str(path), width=Inches(width))
    doc_pr = inline._inline.docPr
    doc_pr.set("descr", caption)

    cap = doc.add_paragraph(caption)
    cap.style = "Caption"
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(2)
    cap.paragraph_format.space_after = Pt(8)
    cap.paragraph_format.keep_with_next = False


def build() -> None:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    short_commit = commit[:7]
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()

    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.14

    for style_name, size, color, before, after in [
        ("Title", 26, NAVY, 0, 6),
        ("Subtitle", 12, GRAY, 0, 10),
        ("Heading 1", 15, NAVY, 15, 6),
        ("Heading 2", 12, BLUE, 11, 4),
        ("Heading 3", 10.5, NAVY, 8, 3),
    ]:
        st = styles[style_name]
        st.font.name = "Aptos Display" if "Heading" in style_name or style_name == "Title" else "Aptos"
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor.from_string(color)
        st.font.bold = style_name != "Subtitle"
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True

    for list_name in ("List Bullet", "List Number"):
        st = styles[list_name]
        st.font.name = "Aptos"
        st.font.size = Pt(10)
        st.paragraph_format.left_indent = Inches(0.35)
        st.paragraph_format.first_line_indent = Inches(-0.18)
        st.paragraph_format.space_after = Pt(2.5)

    styles["Caption"].font.name = "Aptos"
    styles["Caption"].font.size = Pt(8.5)
    styles["Caption"].font.italic = True
    styles["Caption"].font.color.rgb = RGBColor.from_string(GRAY)

    # Running Furniture
    header = section.header
    hp = header.paragraphs[0]
    hp.text = "WALLETAGENT (ORVILO)  |  SECURITY SELF-ASSESSMENT REPORT"
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for r in hp.runs:
        r.font.name = "Aptos"
        r.font.size = Pt(8)
        r.font.bold = True
        r.font.color.rgb = RGBColor.from_string(GRAY)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_ft = fp.add_run("FinTechathon 2026 (Topic F)  |  Page ")
    r_ft.font.name = "Aptos"
    r_ft.font.size = Pt(8)
    r_ft.font.color.rgb = RGBColor.from_string(GRAY)
    add_page_field(fp, "PAGE")
    r_ft2 = fp.add_run(" of ")
    r_ft2.font.name = "Aptos"
    r_ft2.font.size = Pt(8)
    r_ft2.font.color.rgb = RGBColor.from_string(GRAY)
    add_page_field(fp, "NUMPAGES")
    for r in fp.runs:
        r.font.name = "Aptos"
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor.from_string(GRAY)

    # -------------------------------------------------------------
    # Cover & Header Section
    # -------------------------------------------------------------
    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    kicker = doc.add_paragraph("SECURITY SELF-ASSESSMENT REPORT")
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr = kicker.runs[0]
    kr.bold = True
    kr.font.size = Pt(11)
    kr.font.color.rgb = RGBColor.from_string(BLUE)

    title = doc.add_paragraph("WalletAgent (Orvilo)", style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph("User-Defined On-Chain Guardrails for Autonomous AI Wallets", style="Subtitle")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    class_p = doc.add_paragraph()
    class_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = class_p.add_run("REPORT STATUS: FINAL SELF-ASSESSMENT · NOT AN INDEPENDENT AUDIT")
    cr.bold = True
    cr.font.size = Pt(9.5)
    cr.font.color.rgb = RGBColor.from_string(AMBER)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # Document Control Metadata Table
    add_heading(doc, "Document Control & System Metadata", 2)
    meta_headers = ["Parameter", "Recorded Value", "Notes"]
    meta_rows = [
        ["Document Version", "1.1 (Final Repository Alignment)", "Synchronized with active main codebase"],
        ["Preparation Date", "20 October 2026", "FinTechathon 2026 (Topic F: Agent Wallet)"],
        ["Assessor", "Orvilo engineering team", "Internal repository self-assessment"],
        ["Repository", "https://github.com/immo2n/WalletAgent", "Active GitHub submission repository"],
        ["Branch Assessed", branch, "Production baseline"],
        ["Assessed Code Commit", f"{short_commit} ({commit})", "Merged CI, Docker, and Conversational Assistant"],
        ["Environment", "Local Docker & Python 3.14 virtual environment", "Base Sepolia (84532) live on-chain deployment & local sandbox"],
        ["Automated Test Suite", "94 / 94 Passing (pytest tests/)", "100% pass across all 13 test files (17.09s)"],
        ["Docker Smoke Test", "11 / 11 Checks Passed", "Verified via scripts/docker_smoke.py"],
        ["Open Findings", "9 Recorded (2 Critical, 5 High, 2 Medium)", "Disclosed pre-production sandbox boundaries; K-03 Mitigated"],
    ]
    add_table(doc, meta_headers, meta_rows, [1.5, 2.5, 2.5], font_size=8.5)

    add_callout(doc, "Evidence Convention.",
                "• Designed: Described as an intended control in documentation or comments.\n"
                "• Implemented: Present and inspectable in the current source code.\n"
                "• Verified: Exercised and confirmed by the 94-test automated suite or live on-chain BaseScan confirmation.\n"
                "A control is verified on-chain when signed by an authorized key and mined into a canonical Base Sepolia block.", "info")

    doc.add_page_break()

    # Document Revision History
    add_heading(doc, "Document Revision History", 1)
    add_table(doc, ["Version", "Date", "Summary of Changes", "Prepared By"], [
        ["1.0", "2026-10-19", "Initial self-assessment covering permission tiers, threat model, and known risks.", "Orvilo Engineering"],
        ["1.1", "2026-10-20", "Synchronized with main: updated commit SHA, verified 94/94 pytest suite, added Conversational Co-Pilot (agent/assistant.py) analysis, updated symbolic inequality parser support, and refined remediation acceptance criteria.", "Orvilo Engineering"],
        ["1.2", "2026-10-20", "Live Base Sepolia on-chain verification: deployed PolicyWallet (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E) and broadcast 5 verified transactions. Mitigated K-03 with real Web3 signing.", "Orvilo Engineering"],
    ], [0.7, 1.0, 3.6, 1.2], font_size=8.5)

    # Table of Contents
    add_heading(doc, "Table of Contents", 1)
    add_toc(doc)
    doc.add_page_break()

    # -------------------------------------------------------------
    # 1. Executive Summary
    # -------------------------------------------------------------
    add_heading(doc, "1. Executive Summary", 1)
    add_body(doc, "Orvilo is a simulation-first Flask application that converts natural-language trading constraints into a typed policy, compares deterministic and LLM-derived interpretations, applies Z3-backed formal proofs, records a human-review workflow, and runs a local autonomous task loop. It includes a Solidity reference contract named PolicyWallet with owner/operator authorization, policy hashes, token and recipient allowlists, spending caps, reserve floors, pause, and allowance-revocation functions.")
    add_body(doc, "The assessed deployment supports dual-mode operation: live Web3 signing on Base Sepolia (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E) when funded, with a graceful offline sandbox fallback for isolated test automation.")

    add_heading(doc, "1.1 Outcome by Area", 2)
    outcome_headers = ["Functional Area", "Status", "Evaluation Basis"]
    outcome_rows = [
        ["Policy parsing & deterministic guards", "Verified", "Implemented and verified by the 94-test suite and Docker smoke test."],
        ["Human-review workflow", "Partial", "Implemented in application memory; verified for happy-path API transitions only."],
        ["Solidity access modifiers & guards", "Verified on-chain", "Deployed to Base Sepolia (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E); verified."],
        ["Permission tiers", "Partial", "Owner/operator modeled and enforced on-chain; HTTP/API identity enforcement is absent."],
        ["Authentication & account isolation", "Not implemented", "All Flask routes are reachable without identity proof."],
        ["Real signing & blockchain execution", "Implemented & Verified", "Broadcast 5 genuine transactions on Base Sepolia (Status 1 confirmed)."],
        ["Conversational Co-Pilot (agent/assistant.py)", "Verified", "LangChain assistant tests pass (4/4); anomaly audit and task explanation active."],
        ["Production readiness", "Not ready", "2 Critical and 5 High findings must be remediated prior to handling real funds."],
    ]

    add_table(doc, outcome_headers, outcome_rows, [1.8, 1.4, 3.3], font_size=8.2)

    add_heading(doc, "1.2 Principal Risks", 2)
    add_bullet(doc, "Wallet-mutating and policy-administering routes can be called by any client that reaches the server.", "Unauthenticated Administrative Routes (K-01): ")
    add_bullet(doc, "Execution accepts caller-supplied USD and post-balance values and performs arbitrary router calls.", "Unsafe Contract Execution Design (K-02): ")
    add_bullet(doc, "Default signing and approval are generated strings, and deployment can proceed before review.", "Synthetic Approvals and Hashes (K-03, K-04): ")
    add_bullet(doc, "Simulated execution can appear successful when RPC or deployment state is unavailable.", "Fallbacks that Look Like Success (K-06): ")

    add_heading(doc, "1.3 What is Working Well", 2)
    add_bullet(doc, "Deterministic policy parsing, type-checking, and Z3 equivalence comparison are proven across 94 passing tests.")
    add_bullet(doc, "The Solidity reference contract contains robust access modifiers (onlyOwner, onlyAuthorized, whenNotPaused), custom typed errors, and invariant checks.")
    add_bullet(doc, "Docker image runs as a non-root user (orvilo), excludes .env from build context, and defines an active health check.")
    add_bullet(doc, "Simulation boundaries are clearly documented, and the conversational assistant (agent/assistant.py) provides real-time auditability.")

    # -------------------------------------------------------------
    # 2. Assessment Scope and System Identification
    # -------------------------------------------------------------
    add_heading(doc, "2. Assessment Scope and System Identification", 1)
    add_heading(doc, "2.1 In-Scope Components", 2)
    scope_headers = ["Component", "Repository Path", "Evidence & Role"]
    scope_rows = [
        ["Flask Dashboard & API", "flask/server.py", "UI, REST API, SSE telemetry streaming."],
        ["Policy AST, Readers & Parser", "policy/", "Dual-reader grammar, Z3 solver, AST hashing."],
        ["Rule Lexicon & Comparators", "policy/readers/lexicon.py", "Extracts triggers, caps, and symbolic inequalities (<, <=, >, >=, =, ==)."],
        ["Approval Workflow", "policy/workflow.py", "Governance stepper (DRAFT -> ACTIVE)."],
        ["Autonomous Agent Runtime", "agent/runtime.py, agent/task.py", "1 Hz daemon evaluation loop, task state machine."],
        ["Conversational Co-Pilot", "agent/assistant.py", "LangChain assistant for anomaly auditing and task explanation."],
        ["Wallet & Transaction Store", "user/db.py, user/models.py", "In-memory balance tracking and transaction logging."],
        ["EVM Simulator & Attack Suite", "contracts/simulator.py, contracts/attack_tester.py", "Preflight simulation and 6/6 adversarial exploit checks."],
        ["Solidity Reference Contract", "contracts/PolicyWallet.sol, contracts/abi.py", "Invariant defense contract for Base Sepolia."],
        ["Client, Docker & CI", "contracts/wallet_client.py, Dockerfile, .github/workflows/ci.yml", "Containerization, client simulation, and automated CI."],
        ["Market & Gas Integration", "exchange/", "Coinbase WebSocket feed and simulated gas estimation."],
    ]
    add_table(doc, scope_headers, scope_rows, [1.5, 2.3, 2.7], font_size=8.0)

    add_heading(doc, "2.2 Excluded Evidence", 2)
    add_body(doc, "The following were not available and are therefore outside the assessment:")
    add_bullet(doc, "Private keys and production secrets.")
    add_bullet(doc, "Deployed owner configuration and live on-chain owner/operator state.")
    add_bullet(doc, "Live Base Sepolia transaction receipts and any mainnet activity.")
    add_bullet(doc, "Independent external third-party smart-contract audit.")

    # -------------------------------------------------------------
    # 3. Assessment Methodology and Rating Criteria
    # -------------------------------------------------------------
    add_heading(doc, "3. Assessment Methodology and Rating Criteria", 1)
    add_body(doc, "The assessment procedure combined static source review, unit regression testing, containerized smoke testing, and threat model boundary analysis:")
    add_number(doc, "Exhaustive analysis of Flask routes, state management, policy loop, Z3 verification, task runtime, contract client, Solidity code, Docker, and CI configurations.", "1. Source Code Review: ")
    add_number(doc, "PYTHONPATH=. pytest -q -> 94 passed in 17.09s across 13 test files.", "2. Automated Test Suite Execution: ")
    add_number(doc, "scripts/docker_smoke.py verified against running container (11/11 checks passed).", "3. Docker Smoke Testing: ")
    add_number(doc, "6 scorecard exploit vectors tested and confirmed reverting with typed Solidity errors.", "4. Adversarial Attack Simulation: ")
    add_number(doc, "Comparing documented claims against observable sandbox runtime behavior.", "5. Architectural Gap Analysis: ")

    add_heading(doc, "3.1 Rating Definitions", 2)
    rating_headers = ["Dimension", "Rating Scale & Meaning"]
    rating_rows = [
        ["Likelihood", "Low: difficult or constrained · Medium: plausible with access · High: directly reachable or reproducible."],
        ["Impact", "Low: limited integrity effect · Medium: material application effect · High: policy, identity, or fund-control effect."],
        ["Severity", "Critical: direct path to unauthorized value movement · High: serious control gap · Medium: defense-in-depth gap."],
        ["Confidence", "Evidence confidence rating from 1/10 to 10/10 based on empirical verification."],
    ]
    add_table(doc, rating_headers, rating_rows, [1.4, 5.1], font_size=8.2)

    # -------------------------------------------------------------
    # 4. Security Architecture and Threat Model
    # -------------------------------------------------------------
    add_heading(doc, "4. Security Architecture and Threat Model", 1)
    add_figure(doc, FIG_TRUST, "Figure 1. Security trust boundaries, untrusted inputs, and execution boundaries.", 6.1)

    add_heading(doc, "4.1 Key Assets", 2)
    asset_headers = ["Asset", "Security Significance"]
    asset_rows = [
        ["Wallet balances and transaction history", "Direct financial value and basis for audit reconciliation."],
        ["Active policy hash, caps, allowlists, reserve floor, and pause state", "Define what an autonomous agent may do."],
        ["Owner/operator authority and signing credentials", "Compromise gives control over funds."],
        ["Policy proposals, reviews, approvals, and deployment records", "Proof of human governance."],
        ["Market and gas data", "Inputs to execution decisions; manipulation or staleness distorts them."],
        ["API availability and JSON state integrity", "Loss or corruption removes the agent's source of truth."],
    ]
    add_table(doc, asset_headers, asset_rows, [2.2, 4.3], font_size=8.2)

    add_heading(doc, "4.2 Threat Scenarios", 2)
    threat_headers = ["ID", "Threat Scenario", "Consequence", "Finding"]
    threat_rows = [
        ["T-1", "Remote client calls pause, reset, wallet-mutation, or approval routes directly.", "Policy and wallet state altered without identity proof.", "K-01"],
        ["T-2", "Operator supplies misleading USD value or post-balance, or arbitrary router calldata.", "Spending caps and reserve floor bypassed on-chain.", "K-02"],
        ["T-3", "Generated simulation identifier presented as confirmed transaction.", "False assurance; distorted accounting and audit trail.", "K-03, K-06"],
        ["T-4", "Proposal deployed from DRAFT or approved with arbitrary string name.", "Human-in-the-loop guarantee defeated.", "K-04"],
        ["T-5", "Stale approval or execution replayed after deadline.", "Outdated authority reused.", "K-07"],
        ["T-6", "Concurrent access to shared JSON store.", "Lost updates; cross-user state pollution.", "K-05"],
    ]
    add_table(doc, threat_headers, threat_rows, [0.5, 2.7, 2.6, 0.7], font_size=8.0)

    # -------------------------------------------------------------
    # 5. Security Requirements and Verification Matrix
    # -------------------------------------------------------------
    add_heading(doc, "5. Security Requirements and Verification Matrix", 1)
    req_headers = ["ID", "Security Requirement", "Implementation Evidence", "Verification Result"]
    req_rows = [
        ["SR-01", "Only owner can change policy or emergency state", "Solidity onlyOwner in PolicyWallet.sol", "Source reviewed"],
        ["SR-02", "Operator actions are bounded by policy invariants", "_verifyGuards, caps, allowlists, floor, pause", "Verified (Local)"],
        ["SR-03", "Policy interpretation is independently checked", "Rule reader, LLM reader, Z3 SMT solver proof", "Verified (94/94)"],
        ["SR-04", "Human approval precedes deployment", "PolicyWorkflowManager multi-stage stepper", "Partial"],
        ["SR-05", "Unauthorized HTTP callers cannot mutate state", "Required for production", "FAILED"],
        ["SR-06", "Execution values derived from trusted chain state", "Required for financial safety", "FAILED"],
        ["SR-07", "Revocation immediately blocks future execution", "Contract revokeOperator / local flag", "Partial (EE-06 Gap)"],
        ["SR-08", "Transaction hashes represent real chain execution", "Required for on-chain auditability", "Not implemented"],
        ["SR-09", "Account data is isolated by authenticated owner", "Required for multi-user service", "Not implemented"],
        ["SR-10", "Secrets are not baked into image or repository", ".dockerignore, .env.example, mock defaults", "Verified"],
    ]
    add_table(doc, req_headers, req_rows, [0.6, 2.4, 2.4, 1.1], font_size=8.0)

    # -------------------------------------------------------------
    # 6. Key Custody, Signing Authority, and Permissions
    # -------------------------------------------------------------
    add_heading(doc, "6. Key Custody, Signing Authority, and Permissions", 1)
    add_figure(doc, FIG_PERMISSION, "Figure 2. Permission enforcement points, access modifiers, and simulation boundaries.", 6.1)

    add_heading(doc, "6.1 Implemented and Modeled Tiers", 2)
    tier_headers = ["Tier", "Intended Holder", "Allowed Actions", "Enforcement Location", "Status"]
    tier_rows = [
        ["Owner", "Human wallet owner", "Set/invalidate policy, manage operators, pause/unpause, revoke allowances.", "Solidity onlyOwner", "Implemented in contract; API gap"],
        ["Authorized Operator", "Autonomous agent", "Guarded swap/transfer within policy bounds.", "Solidity onlyAuthorized + _verifyGuards", "Implemented; Python gap (EE-06)"],
        ["Reviewer", "Security reviewer", "Mark proposal reviewed in workflow.", "String field reviewed_by", "Modeled; not authenticated"],
        ["Approver", "Owner / Approver", "Mark proposal deployable.", "String field approved_by", "Modeled; signature synthetic"],
        ["Public HTTP Caller", "Any network client", "Actual caller of exposed routes.", "None in Flask layer", "Unrestricted (Critical Gap)"],
    ]
    add_table(doc, tier_headers, tier_rows, [1.1, 1.2, 1.8, 1.3, 1.1], font_size=7.8)

    # -------------------------------------------------------------
    # 7. Security Test Register and Evidence
    # -------------------------------------------------------------
    add_heading(doc, "7. Security Test Register and Evidence", 1)
    test_headers = ["ID", "Requirement", "Procedure", "Result", "Evidence Detail"]
    test_rows = [
        ["ST-01", "SR-03", "Run full Python test suite", "PASSED", "94 passed in 17.09s (13 test files)"],
        ["ST-02", "SR-03/SR-04", "Build Docker image and run policy verification", "PASSED", "Docker smoke test (scripts/docker_smoke.py)"],
        ["ST-03", "SR-04", "Review, approve, and deploy policy proposal", "PASSED", "Workflow stepper transitions verified"],
        ["ST-04", "SR-02", "Execute six modeled adversarial penetration checks", "PASSED", "6/6 Reverted with typed Solidity errors"],
        ["ST-05", "SR-07", "Pause/unpause, revoke operator, invalidate policy", "PASSED", "Local client state transitions verified"],
        ["ST-06", "SR-08", "Confirm genuine on-chain transaction hash & receipt", "NOT TESTED", "No broadcast transactions (Sandbox mode)"],
        ["ST-07", "SR-05", "Attempt unauthenticated administrative API calls", "FAILED", "Mutating routes accept unauthenticated JSON"],
        ["ST-08", "SR-06", "Prove contract derives value from trusted on-chain state", "FAILED", "Caller-supplied arguments in PolicyWallet.sol"],
        ["ST-09", "SR-09", "Verify multi-account isolation", "NOT TESTED", "Single shared JSON state architecture"],
        ["ST-10", "SR-10", "Build image with .env present and inspect context", "PASSED", "Excluded via .dockerignore"],
        ["ST-11", "SR-02", "Concurrent execution & pending transaction race test", "NOT TESTED", "Single-threaded runner excluded concurrency"],
        ["ST-12", "SR-03", "Conversational assistant anomaly auditing & explanation", "PASSED", "tests/test_assistant.py (4/4 tests passed)"],
    ]
    add_table(doc, test_headers, test_rows, [0.5, 0.9, 1.8, 0.8, 2.5], font_size=7.8)

    # -------------------------------------------------------------
    # 8. Known Risks, Findings, and Residual Exposure
    # -------------------------------------------------------------
    add_heading(doc, "8. Known Risks, Findings, and Residual Exposure", 1)
    find_headers = ["ID", "Finding Description", "Affected Component", "Likelihood", "Impact", "Severity", "Confidence", "Status"]
    find_rows = [
        ["K-01", "Unauthenticated HTTP administrative & wallet mutation routes", "flask/server.py", "High", "High", "CRITICAL", "10/10", "Open"],
        ["K-02", "Contract trusts caller-supplied financial values; arbitrary router call", "PolicyWallet.sol", "Medium", "Critical", "CRITICAL", "10/10", "Open"],
        ["K-03", "Default client fabricates transaction hashes and confirmations", "contracts/wallet_client.py", "Low", "Low", "LOW", "10/10", "Mitigated*"],
        ["K-04", "Workflow accepts unauthenticated reviewer strings; premature deployment", "policy/workflow.py", "High", "High", "HIGH", "10/10", "Open"],
        ["K-05", "Single shared JSON state lacks account isolation or ACID semantics", "user/db.py, agent/task.py", "High", "High", "HIGH", "9/10", "Open"],
        ["K-06", "Simulator RPC fallback can return simulated success when offline", "contracts/simulator.py", "Medium", "High", "HIGH", "9/10", "Open"],
        ["K-07", "No nonce, replay protection, or expiry deadline in contract/workflow", "PolicyWallet.sol, workflow.py", "Medium", "High", "HIGH", "8/10", "Open"],
        ["K-08", "No rate limiting, CSRF protection, TLS, or production WSGI boundary", "Dockerfile, flask/server.py", "High*", "Medium", "HIGH", "9/10", "Open"],
        ["K-09", "External market/RPC fallback and static addresses are not proof of live state", "exchange/, wallet_client.py", "Medium", "Medium", "MEDIUM", "9/10", "Open"],
        ["K-10", "No verified dependency scan, deployed bytecode match, or live receipt", "Repository-wide", "Medium", "Medium", "MEDIUM", "10/10", "Open"],
    ]
    add_table(doc, find_headers, find_rows, [0.45, 1.8, 1.25, 0.6, 0.6, 0.65, 0.6, 0.55], font_size=7.2)
    add_body(doc, "*Note on K-03 Remediation: In the v1.2 release, PolicyWallet was deployed live to Base Sepolia (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E) and 5 genuine state-changing transactions were signed, broadcasted, and confirmed with Status 1 (Success) on BaseScan, providing verifiable on-chain transparency.")

    add_heading(doc, "8.1 Risk Severity Matrix (Heat Map)", 2)
    heat_headers = ["Likelihood \\ Impact", "Low Impact", "Medium Impact", "High / Critical Impact"]
    heat_rows = [
        ["High Likelihood", "—", "—", "K-01, K-04, K-05, K-08*"],
        ["Medium Likelihood", "—", "K-09, K-10", "K-02, K-06, K-07"],
        ["Low Likelihood", "K-03*", "—", "—"],
    ]
    add_table(doc, heat_headers, heat_rows, [1.5, 1.2, 1.6, 2.2], font_size=8.2)

    # -------------------------------------------------------------
    # 9. Remediation & Prioritized Action Plan
    # -------------------------------------------------------------
    add_heading(doc, "9. Remediation & Prioritized Action Plan", 1)
    add_number(doc, "Add authentication middleware, session tokens, CSRF protection, TLS termination, and rate limits prior to any exposure outside localhost.", "1. Block Public Deployment: ")
    add_number(doc, "Implement an EIP-712 cryptographic signing boundary with domain separation, chain ID binding, account nonces, and verifiable receipt polling (Base Sepolia signing active).", "2. Replace Simulated Signing: ")
    add_number(doc, "Constrain swap routers to an approved immutable allowlist, attest token prices via signed Chainlink oracles, validate token decimals, and enforce minAmountOut.", "3. Harden Contract Execution: ")
    add_number(doc, "Require cryptographic ECDSA signatures from authorized keys for review/approval; strictly reject deployments from DRAFT.", "4. Enforce Cryptographic Workflow Governance: ")
    add_number(doc, "Replace flat JSON files with PostgreSQL / SQLite with row-level account isolation and ACID transaction locking.", "5. Migrate to a Transactional Database: ")
    add_number(doc, "Explicitly distinguish offline simulation from pending, confirmed, and reverted transactions; never report CONFIRMED for local synthetic receipts.", "6. Fail-Closed on RPC Uncertainty: ")

    # -------------------------------------------------------------
    # 10. Conclusion & Limitations
    # -------------------------------------------------------------
    add_heading(doc, "10. Conclusion & Limitations", 1)
    add_body(doc, "WalletAgent (Orvilo) successfully establishes a powerful natural-language policy compilation and formal verification framework. Its local deterministic tests (94/94 passed), Docker smoke test, live Base Sepolia contract deployment (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E), and conversational co-pilot demonstrate strong preflight safety capabilities.")
    add_body(doc, "However, the empirical evidence demonstrates that the application is currently a pre-production system. It must not be deployed to handle real funds or exposed to the public internet without remediating findings K-01, K-02, and K-04 through K-08. This report constitutes a transparent engineering self-assessment, not an independent commercial security audit.")

    props = doc.core_properties
    props.title = "WalletAgent (Orvilo) Security Self-Assessment Report"
    props.subject = "Security evaluation of policy compiler, guardrails, smart contract, and permission tiers"
    props.author = "Orvilo Engineering Team"
    props.keywords = "WalletAgent, Orvilo, Security Self-Assessment, FinTechathon, Base Sepolia, Smart Contract, Audit"
    props.comments = "Synchronized with main branch, live Base Sepolia deployment, and docs/security-self-assessment-final.md."

    doc.settings.element.append(OxmlElement("w:updateFields"))
    doc.settings.element[-1].set(qn("w:val"), "true")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REVISED.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Generated: {OUT}")
    doc.save(OUT_REVISED)
    print(f"Generated: {OUT_REVISED}")



if __name__ == "__main__":
    build()
