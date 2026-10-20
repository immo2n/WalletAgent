"""Build the publication-grade WalletAgent (Orvilo) Technical Documentation DOCX.

Synchronized with docs/technical-doc-final.md and the active main codebase.
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
OUT = ROOT / "docs/final/Orvilo_Technical_Documentation.docx"
OUT_REVISED = ROOT / "docs/revised/Orvilo_Technical_Documentation.docx"

FIG_POLICY = ROOT / "visuals/rendered/policy-verification.png"
FIG_RUNTIME = ROOT / "visuals/rendered/runtime-safety.png"
FIG_PERMISSION = ROOT / "visuals/rendered/permission-enforcement.png"
FIG_SECURITY = ROOT / "visuals/rendered/security-controls.png"
FIG_DATA = ROOT / "visuals/rendered/data-model.png"
FIG_CONTEXT = ROOT / "visuals/rendered/system-context.png"

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

            # Status styling
            if val_str in ("PASSED", "PASS", "SUCCESS", "Verified", "100% Modeled Reverts", "4/4 Tests Passing"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(GREEN)
                set_cell_shading(cell, LIGHT_GREEN)
            elif val_str in ("FAILED", "FAIL", "CRITICAL"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(RED)
                set_cell_shading(cell, LIGHT_RED)
            elif val_str in ("HIGH", "Partial", "Modeled"):
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(AMBER)
                set_cell_shading(cell, LIGHT_AMBER)
            elif val_str in ("GET", "POST", "MEDIUM", "LOW", "Reference", "Source reviewed"):
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
    hp.text = "WALLETAGENT (ORVILO)  |  TECHNICAL DOCUMENTATION"
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

    kicker = doc.add_paragraph("TECHNICAL DOCUMENTATION & ARCHITECTURE SPECIFICATION")
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr = kicker.runs[0]
    kr.bold = True
    kr.font.size = Pt(11)
    kr.font.color.rgb = RGBColor.from_string(BLUE)

    title = doc.add_paragraph("WalletAgent (Orvilo)", style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph("User-Defined On-Chain Guardrails for Autonomous AI Wallets", style="Subtitle")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    desc = doc.add_paragraph("Architecture, Dual-Reader Formal Verification, Cognitive Reasoning, Smart Contracts, REST API, and Sandbox Evidence")
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    desc.runs[0].font.size = Pt(10.5)
    desc.runs[0].font.color.rgb = RGBColor.from_string(GRAY)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # Metadata Table
    add_heading(doc, "Document Control & System Metadata", 2)
    meta_headers = ["Parameter", "Recorded Value", "Notes"]
    meta_rows = [
        ["Document Version", "1.3 (Live Base Sepolia Alignment)", "Synchronized with active main codebase"],
        ["Preparation Date", "20 October 2026", "FinTechathon 2026 (Topic F: Agent Wallet)"],
        ["Organization", "Orvilo Engineering Team", "Repository technical specification"],
        ["Repository", "https://github.com/immo2n/WalletAgent", "Active GitHub submission repository"],
        ["Branch Assessed", branch, "Production / Submission baseline"],
        ["Assessed Code Commit", f"{short_commit} ({commit})", "Merged CI, Docker, and Conversational Assistant"],
        ["Execution Environment", "Python 3.14 · Linux · Web3 EVM Simulator", "Base Sepolia (84532); Live on-chain & sandbox dual-mode"],
        ["Automated Test Suite", "94 / 94 Passing (pytest tests/)", "100% pass across all 13 test files (17.09s)"],
        ["Docker Smoke Test", "11 / 11 Checks Passed", "Verified via scripts/docker_smoke.py"],
        ["Classification", "Competition Submission & Architecture Spec", "Topic F: Autonomous Agent Wallet"],
    ]
    add_table(doc, meta_headers, meta_rows, [1.5, 2.5, 2.5], font_size=8.5)

    add_callout(doc, "Live On-Chain & Offline Dual-Mode.",
                "PolicyWallet smart contract is deployed on Base Sepolia at 0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E. "
                "The system supports both live Web3 signed transactions on Base Sepolia and offline EVM simulation for local tests.", "success")

    doc.add_page_break()

    # Document Revision History
    add_heading(doc, "Document Revision History", 1)
    add_table(doc, ["Version", "Date", "Summary of Changes", "Prepared By"], [
        ["1.0", "2026-10-19", "Initial technical baseline derived from source inspection and executed tests.", "Orvilo Engineering"],
        ["1.1", "2026-10-19", "Submission edition: added worked examples, capability matrix, and trust model.", "Orvilo Engineering"],
        ["1.2", "2026-10-20", "Final alignment with main: updated commit SHA, verified 94/94 pytest suite, added Conversational Co-Pilot (agent/assistant.py) section, updated symbolic inequality parser documentation (<, <=, >, >=, =, ==), and expanded API reference.", "Orvilo Engineering"],
        ["1.3", "2026-10-20", "Added verified Base Sepolia deployment (0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E) and genuine transaction hash register.", "Orvilo Engineering"],
    ], [0.7, 1.0, 3.6, 1.2], font_size=8.5)

    # Table of Contents
    add_heading(doc, "Table of Contents", 1)
    add_toc(doc)
    doc.add_page_break()

    # -------------------------------------------------------------
    # 1. Executive Summary & Core Innovation
    # -------------------------------------------------------------
    add_heading(doc, "1. Executive Summary & Core Innovation", 1)
    add_body(doc, "Autonomous on-chain agent wallets face a fundamental security dilemma: Large Language Models (LLMs) are uniquely adept at parsing semantic human language and reasoning over volatile market regimes, yet they remain inherently probabilistic, prone to hallucinations, and susceptible to prompt injection attacks. Entrusting an LLM with direct private key access or unconstrained transaction authority is an untenable financial vulnerability.")

    add_body(doc, "WalletAgent (Orvilo) resolves this dilemma through a tri-layer defense-in-depth architecture:", "Tri-Layer Defense Architecture: ")
    add_bullet(doc, "The LLM functions exclusively as an untrusted proposer. It translates conversational intents into formal draft structures, but cannot authorize, execute, or loosen limits.", "1. The LLM is Never the Security Boundary: ")
    add_bullet(doc, "User instructions are parsed across two independent channels (a deterministic spaCy rule parser and a schema-constrained LLM synthesizer). Semantic equivalence is formally proved using the Z3 SMT Solver over physical domain bounds. Disagreements automatically generate concrete counterexamples fed into an automated feedback repair loop.", "2. Dual-Reader Z3 SMT Formal Verification: ")
    add_bullet(doc, "All proposed trades pass through deterministic local invariant gates and EVM pre-execution simulation. The Solidity contract and wallet client define the intended Base Sepolia enforcement boundary.", "3. Deterministic Multi-Stage Enforcement: ")
    add_bullet(doc, "A LangChain-powered conversational co-pilot (agent/assistant.py) provides real-time transaction anomaly auditing, policy invariant explanations, and system telemetry introspection.", "4. Cognitive Conversational Assistant: ")

    # -------------------------------------------------------------
    # 2. FinTechathon 2026 Scorecard: Feature Coverage Matrix
    # -------------------------------------------------------------
    add_heading(doc, "2. FinTechathon 2026 Scorecard: Feature Coverage Matrix", 1)
    add_body(doc, "WalletAgent implements all 9 evaluated scorecard requirements plus the conversational co-pilot:")

    score_headers = ["#", "Scorecard Evaluated Feature", "Primary Implementation Module", "Verification Evidence"]
    score_rows = [
        ["1", "Natural-Language Instruction Parsing & AST Compilation", "policy/readers/rule_reader.py\npolicy/readers/llm_reader.py", "100% AST Paraphrase Hash Equivalence"],
        ["2", "Policy Review & Explicit User Approval Pipeline", "policy/workflow.py\nflask/server.py", "Multi-Step Stepper & Invariant Verification"],
        ["3", "On-Chain Rules: Tokens, Recipients, Caps & Floors", "contracts/PolicyWallet.sol\npolicy/onchain.py", "Invariant Bounds in Solidity & Z3 SMT"],
        ["4", "Scheduled Transfers & Recurring DCA Execution Queue", "agent/task.py\nagent/runtime.py", "Recurring Interval Background Daemon Loop"],
        ["5", "Pre-Execution EVM Simulation & Gas Preflight", "contracts/simulator.py\nreasoning/dry_run.py", "eth_call Revert Trace & Dynamic Buffer"],
        ["6", "Smart Contract On-Chain Policy Invariant Enforcement", "contracts/PolicyWallet.sol\ncontracts/wallet_client.py", "Base Sepolia Tests & Custom Solidity Errors"],
        ["7", "Transaction History, Explanations & Reasoning Audit", "user/db.py\nreasoning/engine.py", "Full RAG & Solver Proof Introspection Modal"],
        ["8", "Emergency Pause, Allowance & Operator Revocation", "contracts/wallet_client.py\ncontracts/PolicyWallet.sol", "Instant Killswitch & Access Control Drops"],
        ["9", "Adversarial Attack Suite (6/6 Exploits Blocked)", "contracts/attack_tester.py\ntests/test_scorecard_features.py", "100% Modeled Reverts with Typed Errors"],
        ["10", "Conversational Assistant & Anomaly Auditor Co-Pilot", "agent/assistant.py\ntests/test_assistant.py", "LangChain Co-Pilot (4/4 Tests Passing)"],
    ]
    add_table(doc, score_headers, score_rows, [0.4, 2.3, 1.9, 1.9], font_size=8.0)

    # -------------------------------------------------------------
    # 3. Master Architecture & Subsystem Index
    # -------------------------------------------------------------
    add_heading(doc, "3. Master Architecture & Subsystem Index", 1)
    add_figure(doc, FIG_POLICY, "Figure 1. Master Pipeline Topology: Dual-reader parsing, Z3 formal verification, and approval workflow.", 6.1)

    subsys_headers = ["Subsystem Area", "Core Modules", "Primary Functionality"]
    subsys_rows = [
        ["Policy Engine & Formal Verification", "policy/ast.py, z3_compile.py, compare.py, loop.py", "Dual readers, AST, dimensional sorts, Z3 SMT solver, counterexamples, hashing."],
        ["Agent Runtime & Cognitive Reasoning", "agent/runtime.py, agent/task.py, reasoning/", "Daemon loop, scheduled DCA queue, market perception, RAG historical regimes, dry-run."],
        ["EVM Smart Contracts & Security Controls", "contracts/PolicyWallet.sol, simulator.py, attack_tester.py", "PolicyWallet.sol, custom typed errors, preflight eth_call, killswitches, attack tester."],
        ["User Approval Workflow & Audit Trail", "policy/workflow.py, user/db.py, flask/server.py", "DRAFT -> ACTIVE stepper, approval signatures, in-memory ledger, Flask UI."],
        ["Security Trust & Permission Model", "contracts/wallet_client.py, visuals/", "Role boundaries, owner/operator tiers, simulation boundary, attack vectors."],
        ["Conversational Co-Pilot Subsystem", "agent/assistant.py", "LangChain router, transaction anomaly auditing, prompt Q&A."],
    ]
    add_table(doc, subsys_headers, subsys_rows, [1.6, 2.3, 2.6], font_size=8.0)

    # -------------------------------------------------------------
    # 4. System Architecture Visualizations
    # -------------------------------------------------------------
    add_heading(doc, "4. System Architecture Visualizations", 1)
    add_figure(doc, FIG_RUNTIME, "Figure 2. Autonomous Agent & Perception Loop: 1 Hz daemon evaluation, market triggers, and preflight simulation.", 6.1)
    add_figure(doc, FIG_PERMISSION, "Figure 3. Permission Enforcement & Trust Boundaries: Access modifiers and local simulation boundaries.", 6.1)

    # -------------------------------------------------------------
    # 5. Detailed Technical Walkthrough of Core Subsystems
    # -------------------------------------------------------------
    add_heading(doc, "5. Detailed Technical Walkthrough of Core Subsystems", 1)

    add_heading(doc, "5.1 Natural-Language Instruction Parsing & Dual-Channel Synthesis", 2)
    add_body(doc, "User instructions are compiled across two independent channels to eliminate single-point-of-failure interpretation errors:")
    add_bullet(doc, "Uses spaCy dependency tree grammars and explicit keyword registries to extract trigger predicates, action clauses, numeric thresholds, and asset symbols. Operates deterministically without network calls.", "Deterministic Rule Reader (policy/readers/rule_reader.py): ")
    add_bullet(doc, "Recognizes both natural-language expressions (under, less than, no more than, at least) and symbolic mathematical operators (<, <=, >, >=, =, ==).", "Symbolic Inequality Parser (policy/readers/lexicon.py): ")
    add_bullet(doc, "Parses colloquial phrasings, synonyms, and conversational variations into a typed Draft-07 JSON Schema.", "Untrusted LLM Synthesizer (policy/readers/llm_reader.py): ")
    add_bullet(doc, "Enforces physical sorts (Sort.USD, Sort.GWEI, Sort.PERCENT, Sort.TOKEN). Rejects nonsensical mathematical comparisons (e.g., comparing Gwei to USD) at compile time via policy/typecheck.py.", "Dimensional Type Checking: ")

    add_heading(doc, "5.2 Formal Verification & Z3 Mathematical Formulation", 2)
    add_body(doc, "Orvilo's formal proof engine proves that two independent natural language interpretations describe identical state-space boundaries:")
    add_code_block(doc, "∀ x ∈ D_physical,  Φ_RuleReader(x) ⟺ Φ_LLMReader(x)")
    add_body(doc, "Where x = <gas, trade, balance_after, daily_spent> represents physical blockchain state variables.")
    add_body(doc, "To verify equivalence, the Z3 solver searches for satisfiability of the refutation predicate:")
    add_code_block(doc, "Ψ_refute = D_physical ∧ ¬(Φ_A ⟺ Φ_B) ≡ D_physical ∧ ((Φ_A ∧ ¬Φ_B) ∨ (¬Φ_A ∧ Φ_B))")
    add_bullet(doc, "No counterexample exists. The two ASTs are provably equivalent under all possible market conditions.", "UNSAT (Unsatisfiable): ")
    add_bullet(doc, "Z3 extracts a concrete counterexample x* (e.g., trade = $250, balance_after = $450). This counterexample is serialized and fed back into Channel B for automated repair (max 2 attempts) before human escalation.", "SAT (Satisfiable): ")

    add_heading(doc, "5.3 Policy Review & Multi-Stage Approval Stepper", 2)
    add_body(doc, "Policies progress strictly through a 4-stage governance pipeline: DRAFT -> REVIEWED -> DEPLOYABLE -> ACTIVE.")
    add_bullet(doc, "Autonomous agents cannot trade against a DRAFT or REVIEWED policy.")
    add_bullet(doc, "Explicit owner signature binds the canonical SHA-256 policy hash.")
    add_bullet(doc, "Deployment updates the in-memory PolicyWalletClient guard state and registers the agent daemon task.")

    add_heading(doc, "5.4 On-Chain Invariants & Smart Contract Guardrails", 2)
    add_body(doc, "The reference Solidity contract (contracts/PolicyWallet.sol) enforces invariant security at the EVM level:")
    add_number(doc, "Only whitelisted ERC-20 tokens (ETH, WETH, USDC) can be traded. All other tokens revert with TokenNotAllowed(address).", "1. Token Allowlist: ")
    add_number(doc, "Outgoing transfers are restricted to approved counterparty addresses; unapproved destinations revert with RecipientNotAllowed(address).", "2. Recipient Allowlist: ")
    add_number(doc, "Bounds single-trade exposure (e.g., $300 max per trade); reverts with ExceedsPerTxCap(amount, cap).", "3. Per-Transaction Cap: ")
    add_number(doc, "Tracks 24-hour daily spend; reverts with ExceedsDailyLimit(spent, limit) if breached.", "4. 24-Hour Rolling Daily Cap: ")
    add_number(doc, "Reverts with BelowMinimumBalanceFloor(balance, floor) if projected post-execution balance drops below the verified floor (e.g., $500).", "5. Minimum Balance Reserve Floor: ")
    add_number(doc, "pause() immediately locks all outgoing transactions; revokeOperator() drops autonomous execution rights.", "6. Emergency Killswitch: ")

    add_heading(doc, "5.5 Autonomous Agent Runtime & DCA Task Queue", 2)
    add_body(doc, "The autonomous daemon (agent/runtime.py) operates at 1 Hz:")
    add_bullet(doc, "Supports IMMEDIATE, CONDITIONAL_TRIGGER, and RECURRING_INTERVAL schedules.")
    add_bullet(doc, "Enables recurring Dollar-Cost Averaging (e.g., Buy $100 USDC of ETH every 60 seconds while gas <= 20 gwei).")
    add_bullet(doc, "Automatically executes swaps as interval timestamps mature while strictly honoring all policy caps.")

    add_heading(doc, "5.6 Conversational Assistant & Anomaly Auditor Co-Pilot", 2)
    add_body(doc, "The LangChain assistant (agent/assistant.py) provides natural language co-pilot capabilities:")
    add_bullet(doc, "Inspects historical and pending transactions, identifying transfers to unwhitelisted addresses, spending spikes, or reserve floor breaches.", "Transaction Anomaly Auditing: ")
    add_bullet(doc, "Breaks down active autonomous DCA tasks, explaining remaining intervals, gas triggers, and invariant constraints in plain English.", "Task Explanation: ")
    add_bullet(doc, "Accessible via the responsive floating chat bubble on the web dashboard.", "Interactive Web Interface: ")
    add_bullet(doc, "Leverages structured tool routing with automatic fallback to offline deterministic analysis when external LLM endpoints are unreachable.", "LangChain Integration: ")

    # -------------------------------------------------------------
    # 6. Complete REST API Reference
    # -------------------------------------------------------------
    add_heading(doc, "6. Complete REST API Reference", 1)
    add_body(doc, "The Flask application (flask/server.py) exposes 23 endpoints:")

    api_headers = ["Endpoint", "Method", "Role / Description", "Status"]
    api_rows = [
        ["/", "GET", "Responsive web dashboard UI", "Verified"],
        ["/api/market/stream", "GET", "Server-Sent Events (SSE) telemetry stream", "Verified"],
        ["/api/market/state", "GET", "Snapshot of live Coinbase prices & gas oracle", "Verified"],
        ["/api/wallet/state", "GET", "Wallet balances, active policy, & guard state", "Verified"],
        ["/api/wallet/simulate-trade", "POST", "Preflight EVM simulation & dry-run execution", "Verified"],
        ["/api/reasoning/audit", "GET", "Complete transaction reasoning proof traces", "Verified"],
        ["/api/wallet/reset", "POST", "Reinitializes simulation state to defaults", "Verified"],
        ["/api/verify", "POST", "Natural-language policy compilation & Z3 proof", "Verified"],
        ["/api/policy/workflow", "GET", "Current governance proposal status", "Verified"],
        ["/api/policy/review", "POST", "Moves policy proposal from DRAFT to REVIEWED", "Verified"],
        ["/api/policy/approve", "POST", "Generates approval signature (DEPLOYABLE)", "Verified"],
        ["/api/policy/deploy", "POST", "Activates policy and registers autonomous task", "Verified"],
        ["/api/agent/task", "POST", "Manually configures or updates agent DCA task", "Verified"],
        ["/api/agent/pause", "POST", "Pauses autonomous agent daemon loop", "Verified"],
        ["/api/agent/resume", "POST", "Resumes autonomous agent daemon loop", "Verified"],
        ["/api/contract/pause", "POST", "Activates smart contract emergency pause", "Verified"],
        ["/api/contract/unpause", "POST", "Deactivates emergency pause", "Verified"],
        ["/api/contract/revoke-operator", "POST", "Revokes agent operator authorization", "Verified"],
        ["/api/contract/revoke-allowance", "POST", "Resets DEX router token allowances to zero", "Verified"],
        ["/api/contract/invalidate-policy", "POST", "Invalidates active policy hash", "Verified"],
        ["/api/contract/test-attacks", "POST", "Executes 6-vector adversarial attack suite", "Verified"],
        ["/api/assistant/chat", "POST", "Conversational assistant Q&A and task explanation", "Verified"],
        ["/api/assistant/audit", "POST", "Anomaly transaction analysis & risk report", "Verified"],
    ]
    add_table(doc, api_headers, api_rows, [2.0, 0.7, 3.0, 0.8], font_size=7.8)

    # -------------------------------------------------------------
    # 7. Automated Test Suite Evidence
    # -------------------------------------------------------------
    add_heading(doc, "7. Automated Test Suite Evidence", 1)
    add_body(doc, "The complete test suite contains 94 automated unit and integration tests across 13 test files:")
    add_code_block(doc, "PYTHONPATH=. .venv/bin/python -m pytest -q")

    test_console = (
        "============================= test session starts ==============================\n"
        "platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0\n"
        "rootdir: /home/immo2n/Moon/WalletAgent\n"
        "plugins: anyio-4.15.1, langsmith-0.14.11\n"
        "collected 94 items\n\n"
        "tests/policy/test_compile_compare.py ...                                 [  3%]\n"
        "tests/policy/test_loop.py ......                                         [  9%]\n"
        "tests/policy/test_mutations.py ...........                               [ 21%]\n"
        "tests/policy/test_paraphrase_hash.py ...                                 [ 24%]\n"
        "tests/policy/test_prompts_t1.py ..........                               [ 35%]\n"
        "tests/policy/test_readback.py ..                                         [ 37%]\n"
        "tests/policy/test_readers_llm_mock.py ...                                [ 40%]\n"
        "tests/policy/test_readers_rule.py .........                              [ 50%]\n"
        "tests/policy/test_sanity.py ....                                         [ 54%]\n"
        "tests/policy/test_sorts_ast.py ....                                      [ 58%]\n"
        "tests/policy/test_typecheck.py .....                                     [ 63%]\n"
        "tests/test_agent.py ....                                                 [ 68%]\n"
        "tests/test_assistant.py ....                                             [ 72%]\n"
        "tests/test_exchange.py ...                                               [ 75%]\n"
        "tests/test_reasoning.py ........                                         [ 84%]\n"
        "tests/test_scorecard_features.py ...........                             [ 95%]\n"
        "tests/test_user_db.py ....                                               [100%]\n\n"
        "============================= 94 passed in 17.09s =============================="
    )
    add_code_block(doc, test_console)
    add_body(doc, "Result: 94 passed in 17.09 seconds. 100% test pass rate with zero regressions.")

    # -------------------------------------------------------------
    # 8. Deployment & Reproduction Instructions
    # -------------------------------------------------------------
    add_heading(doc, "8. Deployment & Reproduction Instructions", 1)
    add_number(doc, "Python 3.10+ (tested on Python 3.11 - 3.14); Docker & Docker Compose.", "1. Prerequisites: ")
    add_number(doc, "Configure .env with LLM_PROVIDER=mock, CHAIN_ID=84532, RPC_URL=https://sepolia.base.org, and WALLET_CONTRACT_ADDRESS=0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E.", "2. Environment Setup: ")
    add_number(doc, "Launch locally: PYTHONPATH=. python main.py --host 127.0.0.1 --port 5000", "3. Local Execution: ")
    add_number(doc, "Validate via Docker: python scripts/docker_smoke.py http://127.0.0.1:5000 (11/11 checks pass).", "4. Container Validation: ")

    add_heading(doc, "8.1 Live Base Sepolia Verified Contract & Transactions", 2)
    add_body(doc, "The PolicyWallet contract is live on Base Sepolia. The table below documents the verified on-chain deployment and initial transactions:")
    tx_headers = ["#", "Action Description", "Block", "Gas Used", "BaseScan Explorer Transaction Link"]
    tx_rows = [
        ["1", "Deploy PolicyWallet Contract", "#48349779", "2,025,439", "https://sepolia.basescan.org/tx/b3a5e3044fa1ed5f0b40da4573bd1a6f68e2dd6290bfb17f7693b7a705624a40"],
        ["2", "Set Verified Policy (setPolicy)", "#48349781", "160,292", "https://sepolia.basescan.org/tx/42a5e6e3140a3954e118cc8961a322a65cded9dd60e64a0538805d704e6c6400"],
        ["3", "Emergency Pause Killswitch (pause)", "#48349783", "45,073", "https://sepolia.basescan.org/tx/dd853edcaa73408046a2aff4c5b0f92d94d8ae805a433d66c3eb210bf67bd9a3"],
        ["4", "Lift Emergency Pause (unpause)", "#48349785", "23,194", "https://sepolia.basescan.org/tx/38fca19438151fe9f56f206cd285c8a23a365fae771650f659232e53cc738822"],
        ["5", "Authorize Operator (setOperator)", "#48349787", "46,087", "https://sepolia.basescan.org/tx/e7da3881004d6b7cd14fae51a6900c5904c1039e608a3fd2f8057fe1635f690f"],
    ]
    add_table(doc, tx_headers, tx_rows, [0.4, 2.0, 0.9, 0.9, 2.3], font_size=8.0)

    props = doc.core_properties
    props.title = "WalletAgent (Orvilo) Technical Documentation"
    props.subject = "Architecture, formal verification, cognitive reasoning, smart contracts, and REST API specification"
    props.author = "Orvilo Engineering Team"
    props.keywords = "WalletAgent, Orvilo, Technical Documentation, FinTechathon, Base Sepolia, Z3, Guardrails"
    props.comments = "Synchronized with main branch, live Base Sepolia deployment, and docs/technical-doc-final.md."

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

