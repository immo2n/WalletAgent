"""Build the polished Orvilo Execution Evidence Report DOCX."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/execution-report/execution-evidence.json"
OUT = ROOT / "docs/Orvilo_Execution_Evidence_Report.docx"
FIG_SYSTEM = ROOT / "visuals/rendered/system-context.png"
FIG_PERMISSION = ROOT / "visuals/rendered/permission-enforcement.png"

NAVY = "17324D"
BLUE = "1E5A88"
LIGHT_BLUE = "EAF2F8"
PALE = "F4F6F8"
GRAY = "5B6570"
LIGHT_GRAY = "D9E0E6"
GREEN = "176B3A"
RED = "9B1C1C"
AMBER = "7A5A00"
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
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
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
    table.style = "Table Grid"
    set_table_widths(table, widths)
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_shading(cell, NAVY)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        r.bold = True
        r.font.color.rgb = RGBColor.from_string(WHITE)
        r.font.size = Pt(font_size)
    for row_values in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row_values):
            cell = cells[i]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if len(table.rows) % 2 == 1:
                set_cell_shading(cell, PALE)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(value))
            r.font.size = Pt(font_size)
            r.font.color.rgb = RGBColor.from_string(BLACK)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
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
    run = p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Right-click and choose Update Field to refresh this table of contents."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, placeholder, end])


def add_heading(doc, text: str, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def add_body(doc, text: str, bold_lead: str | None = None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_bullet(doc, text: str):
    return doc.add_paragraph(text, style="List Bullet")


def add_number(doc, text: str):
    return doc.add_paragraph(text, style="List Number")


def add_callout(doc, label: str, text: str, color=AMBER):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.right_indent = Inches(0.12)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), LIGHT_BLUE if color != RED else "FDECEC")
    p_pr.append(shd)
    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), color)
    borders.append(left)
    p_pr.append(borders)
    r = p.add_run(label + " ")
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(color)
    p.add_run(text)


def add_figure(doc, path: Path, caption: str, width=6.1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    inline = run.add_picture(str(path), width=Inches(width))
    doc_pr = inline._inline.docPr
    doc_pr.set("descr", caption)
    cap = doc.add_paragraph(caption)
    cap.style = "Caption"
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.keep_with_next = False


def outcome_text(value: str) -> str:
    return {"PASSED": "Passed", "FAILED": "Failed", "NOT EXECUTED": "Not executed"}.get(value, value.title())


def compact_observation(s: dict) -> str:
    obs = s["observed_result"]
    if s["scenario_id"] == "EE-04":
        return "States: " + " -> ".join(obs["states"]) + "; signature and deployment ID synthetic."
    if s["scenario_id"] == "EE-06":
        status = obs["post_revocation_execution_response"].get("status")
        return f"Operator marked unauthorized, but local execution returned {status}; no broadcast occurred."
    if s["scenario_id"] == "EE-07":
        return "6/6 modeled vectors returned the expected simulated reverts."
    return f"{obs.get('status', 'Recorded')}: {obs.get('revert_reason') or 'guard evaluation completed'}"


def build() -> None:
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    run_date = data["run_started_utc"][:10]
    checksum = (EVIDENCE.parent / "execution-evidence.sha256").read_text(encoding="utf-8").split()[0]

    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(BLACK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.14
    for style_name, size, color, before, after in [
        ("Title", 28, NAVY, 0, 10), ("Subtitle", 13, GRAY, 0, 8),
        ("Heading 1", 16, NAVY, 16, 7), ("Heading 2", 12.5, BLUE, 11, 5),
        ("Heading 3", 11, NAVY, 8, 4),
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
        st.font.size = Pt(10.5)
        st.paragraph_format.left_indent = Inches(0.35)
        st.paragraph_format.first_line_indent = Inches(-0.18)
        st.paragraph_format.space_after = Pt(3)
    styles["Caption"].font.name = "Aptos"
    styles["Caption"].font.size = Pt(9)
    styles["Caption"].font.italic = True
    styles["Caption"].font.color.rgb = RGBColor.from_string(GRAY)

    # Running furniture.
    header = section.header
    hp = header.paragraphs[0]
    hp.text = "ORVILO  |  EXECUTION EVIDENCE REPORT"
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for r in hp.runs:
        r.font.name = "Aptos"
        r.font.size = Pt(8)
        r.font.bold = True
        r.font.color.rgb = RGBColor.from_string(GRAY)
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fp.add_run("Repository self-assessment  |  Page ")
    add_page_field(fp, "PAGE")
    fp.add_run(" of ")
    add_page_field(fp, "NUMPAGES")
    for r in fp.runs:
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor.from_string(GRAY)

    # Cover.
    doc.add_paragraph().paragraph_format.space_after = Pt(72)
    kicker = doc.add_paragraph("EXECUTION EVIDENCE")
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr = kicker.runs[0]
    kr.bold = True
    kr.font.size = Pt(11)
    kr.font.color.rgb = RGBColor.from_string(BLUE)
    title = doc.add_paragraph("Orvilo", style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = doc.add_paragraph("Execution Evidence Report", style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line = doc.add_paragraph("Sandbox verification of policy, guardrail, workflow, and revocation behavior")
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line.runs[0].font.size = Pt(11)
    line.runs[0].font.color.rgb = RGBColor.from_string(GRAY)
    doc.add_paragraph().paragraph_format.space_after = Pt(28)
    add_table(doc, ["Document field", "Value"], [
        ["Report version", "1.0"], ["Preparation date", "19 October 2026"],
        ["Evidence execution date", run_date + " (UTC)"],
        ["Team", "Orvilo engineering team; individual names not present in repository evidence"],
        ["Repository", "https://github.com/immo2n/WalletAgent"], ["Branch", branch],
        ["Assessed commit", commit], ["Submission category", "Non-on-chain topic / sandbox evidence"],
        ["Environment", "Local Python sandbox; mock LLM; offline deterministic EVM guard simulation"],
    ], [1.55, 4.95], 9)
    add_callout(doc, "Evidence status.", "No signed transaction was submitted to Base Sepolia or any other chain during this evidence run. Hash-like values returned by the application are synthetic identifiers and are not transaction receipts.", RED)
    doc.add_page_break()

    add_heading(doc, "Document control", 1)
    add_table(doc, ["Version", "Date", "Change", "Prepared by"], [
        ["1.0", "2026-10-19", "Initial execution evidence report based on isolated run and repository review", "Orvilo engineering / Codex-assisted documentation"],
    ], [0.7, 1.0, 3.7, 1.1], 8.5)
    add_heading(doc, "Table of contents", 1)
    add_toc(doc)
    doc.add_page_break()

    add_heading(doc, "1. Purpose and Evidence Scope", 1)
    add_body(doc, "This report records repeatable execution evidence for the current Orvilo repository. It demonstrates implemented policy-guard evaluation, workflow state transitions, simulated attack rejection, emergency pause behavior, and permission revocation behavior. The evidence is intended to show what the software actually did in the assessed sandbox, not what a future production deployment is expected to do.")
    add_callout(doc, "Submission classification.", "The defensible category is non-on-chain sandbox evidence. Although the application labels its network Base Sepolia (chain ID 84532), the default client generates UUID-based hash-like identifiers and does not sign, submit, poll, or verify blockchain transactions.", RED)
    add_body(doc, "Covered workflows:")
    for item in [
        "Authorized operation accepted by local policy guards.",
        "Per-transaction limit and recipient allowlist rejection.",
        "Draft, review, approval, deployable, and active workflow transitions.",
        "Emergency pause rejection and six modeled adversarial checks.",
        "Post-revocation execution attempt, including the observed enforcement gap.",
        "Repository automated tests (90 passed).",
    ]:
        add_bullet(doc, item)
    add_body(doc, "Excluded or unavailable evidence includes genuine private-key signing, transaction submission, transaction receipts, block inclusion, deployed bytecode verification, live account balances, a supplied demo video, production authentication, multi-user account isolation, and mainnet execution.")

    add_heading(doc, "2. Application Version and Execution Environment", 1)
    add_table(doc, ["Attribute", "Recorded value"], [
        ["Source commit", commit], ["Branch", branch], ["Evidence run", data["run_started_utc"] + " to " + data["run_completed_utc"]],
        ["Runtime", "Python 3.13 project virtual environment"], ["LLM mode", "Mock/offline by default"],
        ["Persistence used", "None for evidence scenarios; fresh in-memory objects"],
        ["Blockchain network label", "Base Sepolia; chain ID 84532"], ["RPC in evidence run", "Disabled by explicit offline Web3 stub"],
        ["Deployment environment", "Local repository workspace; no public service deployment"],
        ["Automated test result", "90 passed in 3.21 seconds"],
    ], [1.75, 4.75], 8.7)
    add_body(doc, "The evidence generator deliberately avoids the mutable repository JSON stores and Flask routes. This preserves the user's existing wallet and task state and prevents local sandbox activity from being confused with chain settlement.")

    add_heading(doc, "3. Deployed Components and Test Accounts", 1)
    add_figure(doc, FIG_SYSTEM, "Figure 1. Orvilo implementation context and external dependencies (repository architecture).", 6.1)
    add_table(doc, ["Component", "Execution role", "Evidence status"], [
        ["EVMSimulator", "Local policy and guard evaluation; optional eth_call path", "Executed with RPC explicitly offline"],
        ["PolicyWorkflowManager", "Proposal review, approval, and activation states", "Executed in memory"],
        ["PolicyWalletClient", "Local security state and synthetic transaction responses", "Executed; no signing/broadcast"],
        ["AttackSimulator", "Six modeled guardrail violations", "Executed in memory"],
        ["Flask dashboard", "User interface and API", "Source reviewed; not used in isolated evidence run"],
        ["PolicyWallet.sol", "Reference Solidity enforcement", "Source reviewed; deployed bytecode not verified"],
    ], [1.45, 3.15, 1.9], 8.2)
    add_heading(doc, "Accounts and permission tiers", 2)
    add_table(doc, ["Public identifier", "Role/tier", "Observed authority", "Credential handling"], [
        ["0x71C8...039A", "Owner / default sender label", "Owner-equivalent in local defaults; owner-only in Solidity source", "No private key available or used"],
        ["0x2B5A...D6cF", "Autonomous agent operator", "Local authorization flag can be revoked; local execution path does not enforce the flag", "No private key available or used"],
        ["0x89D2...0359", "Default contract-address label", "Destination label in local responses", "Deployment and bytecode not verified"],
    ], [1.25, 1.25, 2.85, 1.15], 7.8)

    add_heading(doc, "4. Execution Scenario Register", 1)
    register_rows = []
    for s in scenarios:
        register_rows.append([
            s["scenario_id"], s["feature"], s["expected_result"], compact_observation(s), outcome_text(s["outcome"]),
            f"EV-LOG-01 / JSON scenario {s['scenario_id']}",
        ])
    add_table(doc, ["ID", "Feature", "Expected", "Actual", "Outcome", "Evidence"], register_rows,
              [0.45, 1.2, 1.35, 1.9, 0.65, 0.95], 7.2)
    add_body(doc, "Not executed: expired/reused approval rejection and concurrent aggregate-limit behavior. The implementation lacks approval expiry/reuse binding, and this evidence run did not claim a concurrency result without a dedicated test.")

    add_heading(doc, "5. Detailed Execution Records", 1)
    for s in scenarios:
        add_heading(doc, f"{s['scenario_id']} - {s['feature']}", 2)
        add_table(doc, ["Record item", "Evidence"], [
            ["Objective", s["expected_result"]],
            ["Starting state", json.dumps(s["before_state"], sort_keys=True)],
            ["Inputs/actions", json.dumps(s["inputs"], sort_keys=True)],
            ["Policy/approval checks", "Local deterministic checks; no authenticated identity and no blockchain signer"],
            ["Observed response", compact_observation(s)],
            ["Resulting state", json.dumps(s["after_state"], sort_keys=True)],
            ["Outcome", outcome_text(s["outcome"])],
            ["Evidence reference", f"EV-LOG-01, scenarios[{s['scenario_id']}]"],
        ], [1.35, 5.15], 8.1)
        if s["scenario_id"] == "EE-06":
            add_callout(doc, "Failed control evidence.", "The operator flag changed from true to false, but the Python execution method selected a local sender without checking authorization and returned a synthetic CONFIRMED response. This is an implementation gap, not evidence of successful on-chain execution.", RED)

    add_heading(doc, "6. On-Chain Transaction Evidence", 1)
    add_callout(doc, "No genuine on-chain evidence available.", "Zero transactions were signed or broadcast, so there are no valid transaction hashes, receipts, block timestamps, contract events, fee records, or verified state changes to report.", RED)
    add_table(doc, ["Required field", "Evidence status"], [
        ["Network and chain ID", "Application configuration states Base Sepolia (84532)"],
        ["Sender / destination", "Only static labels are present; signer ownership was not proven"],
        ["Transaction hash", "Unavailable; application responses are synthetic UUID-derived strings"],
        ["Receipt status", "Unavailable"], ["Block number / timestamp", "Unavailable; locally returned block numbers are simulated"],
        ["Events and state change", "Unavailable"], ["Explorer link", "Generated links are not accepted as evidence without a matching genuine receipt"],
    ], [2.0, 4.5], 8.8)
    add_body(doc, "A future on-chain submission should capture the signed payload, sender, chain ID, nonce, genuine transaction hash, receipt status, block number, timestamp, decoded events, before/after chain state, and explorer link for each scenario. Reverted transactions must be distinguished from application-level rejections that never reach the chain.")

    add_heading(doc, "7. Sandbox or Simulated-Account Operation Logs", 1)
    add_body(doc, "EV-LOG-01 is the canonical structured log. Every record contains an ISO 8601 UTC timestamp, scenario identifier, inputs, expected and observed results, before/after state, outcome, and an explicit LOCAL_SANDBOX_SIMULATION label.")
    add_table(doc, ["Log attribute", "Value"], [
        ["File", "docs/evidence/execution-report/execution-evidence.json"],
        ["SHA-256", checksum], ["Scenario count", str(len(scenarios))],
        ["RPC used", "No"], ["Transactions broadcast", "0"],
        ["Sensitive data", "No credentials or private keys captured"],
    ], [1.5, 5.0], 8.7)
    add_heading(doc, "Representative observed results", 2)
    add_table(doc, ["Scenario", "Status / decision", "State mutation"], [
        ["EE-01", "SIMULATED_SUCCESS; projected $200 change; estimated gas 84,500", "No chain mutation"],
        ["EE-02", "SIMULATED_REVERT: ExceedsPerTxCap(amount=700, cap=500)", "None"],
        ["EE-03", "SIMULATED_REVERT: RecipientNotAllowed", "None"],
        ["EE-05", "SIMULATED_REVERT: WalletPaused", "None"],
        ["EE-07", "Six modeled vectors rejected as expected", "None"],
    ], [0.7, 4.2, 1.6], 8.3)

    add_heading(doc, "8. Permission and Guardrail Execution Evidence", 1)
    add_figure(doc, FIG_PERMISSION, "Figure 2. Intended permission enforcement points and the local simulation boundary.", 6.15)
    add_table(doc, ["Required demonstration", "Scenario", "Observed result", "Assessment"], [
        ["Authorized operation completes", "EE-01", "Local guards returned SIMULATED_SUCCESS", "Passed in sandbox only"],
        ["Spending limit rejected", "EE-02", "ExceedsPerTxCap", "Passed"],
        ["Restricted destination blocked", "EE-03", "RecipientNotAllowed", "Passed"],
        ["User approval required", "EE-04", "State transition recorded, but actor labels/signature are unverified", "Partial demonstration"],
        ["Expired or reused approval rejected", "Not executed", "No expiry/reuse control in assessed workflow", "Unavailable"],
        ["Attempt after permission revocation", "EE-06", "Local client still returned synthetic CONFIRMED", "Failed"],
        ["Concurrent aggregate-limit interaction", "Not executed", "No dedicated concurrency evidence", "Unavailable"],
    ], [1.85, 0.75, 2.6, 1.3], 7.8)

    add_heading(doc, "9. Before-and-After State Verification", 1)
    add_table(doc, ["Scenario", "Before", "After", "Verified interpretation"], [
        ["EE-01", "Projected balance $1,500; spend $0", "Projected balance $1,300; spend counter unchanged", "Simulation result only"],
        ["EE-02", "No chain mutation", "No chain mutation", "Cap violation rejected before RPC"],
        ["EE-03", "No chain mutation", "No chain mutation", "Recipient violation rejected before RPC"],
        ["EE-04", "DRAFT", "ACTIVE", "In-memory workflow changed; no chain state"],
        ["EE-05", "Paused", "Paused; no chain mutation", "Operation rejected"],
        ["EE-06", "Agent authorized=true", "Agent authorized=false; execution still reported CONFIRMED", "Revocation recorded but not locally enforced"],
        ["EE-07", "No chain mutation", "No chain mutation", "Modeled attacks only"],
    ], [0.65, 1.75, 2.25, 1.85], 7.8)
    add_body(doc, "No fee reconciliation was possible because no transaction entered a mempool or block. Gas and balance values in the log are estimates or projected state, not observed blockchain state.")

    add_heading(doc, "10. Demo Video and Evidence Walkthrough", 1)
    add_callout(doc, "Recorded demonstration.", "A five-minute demo has been recorded. The video is submitted separately; its filename or public link is not stored in this repository. The final segment explicitly discloses that the run is sandbox evidence and produced no genuine blockchain transaction.", AMBER)
    add_table(doc, ["Timestamp", "Scenario(s)", "Demonstrated content"], [
        ["00:00-00:15", "Context", "Application dashboard and environment"],
        ["00:15-00:35", "Initial state", "Wallet balance and initial state"],
        ["00:35-01:10", "Policy", "Policy creation and verification"],
        ["01:10-01:35", "EE-04", "Policy review and approval"],
        ["01:35-02:05", "EE-01", "Authorized simulated operation"],
        ["02:05-02:35", "EE-02", "Spending-limit rejection"],
        ["02:35-03:05", "EE-03", "Restricted-recipient rejection"],
        ["03:05-03:30", "EE-05", "Emergency-pause rejection"],
        ["03:30-03:55", "EE-06", "Permission/operator revocation"],
        ["03:55-04:35", "EE-07", "Attack simulation results"],
        ["04:35-05:00", "Conclusion", "Transaction history, logs, final state, and sandbox-evidence disclosure"],
    ], [1.15, 1.15, 4.2], 8.2)

    add_heading(doc, "11. Execution Results and Limitations", 1)
    add_table(doc, ["Result class", "Count", "Details"], [
        ["Passed", "6", "EE-01 through EE-05 and EE-07"],
        ["Failed", "1", "EE-06: post-revocation local execution was not rejected"],
        ["Not executed", "2", "Approval expiry/reuse and concurrent aggregate-limit behavior"],
        ["Automated tests", "90 passed", "Repository pytest suite"],
        ["Genuine on-chain transactions", "0", "No signer or broadcast path exercised"],
    ], [1.7, 1.0, 3.8], 8.6)
    add_body(doc, "Successful demonstrations establish only that the current local code produced the recorded responses under controlled inputs. They do not establish production security, correctness under concurrency, deployment integrity, authenticated authorization, live market accuracy, reliable settlement, or safety for real funds.")
    add_body(doc, "Primary limitations:")
    for item in [
        "The Python wallet client fabricates confirmation data instead of signing and broadcasting.",
        "The local revocation flag is not consulted by the Python execution method.",
        "Workflow reviewers, approvers, and signatures are strings rather than authenticated cryptographic approvals.",
        "The simulator can fall back to success-oriented estimates when RPC is unavailable; this report disables RPC and labels the result accordingly.",
        "The reference contract was not compiled, deployed, bytecode-matched, or exercised in this run.",
        "No demo video was supplied, and no production account credentials were available.",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "12. Evidence Index and Reproduction Instructions", 1)
    add_table(doc, ["Evidence ID", "Artifact", "Purpose", "Integrity/status"], [
        ["EV-LOG-01", "execution-evidence.json", "Structured scenario log", "SHA-256: " + checksum],
        ["EV-HASH-01", "execution-evidence.sha256", "Integrity sidecar", "Generated with SHA-256"],
        ["EV-TEST-01", "pytest console result", "Regression evidence", "90 passed"],
        ["EV-FIG-01", "system-context.png", "Architecture context", "Repository visual"],
        ["EV-FIG-02", "permission-enforcement.png", "Permission boundary context", "Repository visual"],
        ["EV-VIDEO-01", "Five-minute demo video", "Timestamped walkthrough", "Recorded; submitted separately; link not stored"],
        ["EV-CHAIN-01", "Transaction receipts", "Required for on-chain category", "Unavailable"],
    ], [0.9, 1.65, 2.45, 1.5], 8.0)
    add_heading(doc, "Reproduction", 2)
    for step in [
        "Use Python 3.13 and install requirements from requirements.txt in an isolated environment.",
        "From the repository root, run: .venv/bin/python scripts/generate_execution_evidence.py",
        "Verify integrity using the SHA-256 value in docs/evidence/execution-report/execution-evidence.sha256.",
        "Run the regression suite: .venv/bin/python -m pytest -q",
        "Review the JSON fields evidence_classification, rpc_used_for_this_run, and genuine_transactions_broadcast before submission.",
    ]:
        add_number(doc, step)
    add_callout(doc, "Safety note.", "Do not insert private keys into the evidence generator. Genuine chain evidence requires a separately designed signer/broadcast/receipt-verification path and should be collected on an explicitly approved network.", RED)

    add_heading(doc, "13. Appendices and Supporting Files", 1)
    add_heading(doc, "Appendix A - Source map", 2)
    add_table(doc, ["Area", "Repository source"], [
        ["Evidence generator", "scripts/generate_execution_evidence.py"],
        ["Policy simulator", "contracts/simulator.py"], ["Local wallet client", "contracts/wallet_client.py"],
        ["Attack scenarios", "contracts/attack_tester.py"], ["Approval workflow", "policy/workflow.py"],
        ["Reference smart contract", "contracts/PolicyWallet.sol"], ["Test suite", "tests/"],
        ["Container smoke workflow", "scripts/docker_smoke.py and .github/workflows/ci.yml"],
    ], [2.0, 4.5], 8.7)
    add_heading(doc, "Appendix B - Evidence checksum", 2)
    add_body(doc, "SHA-256 (execution-evidence.json):")
    p = doc.add_paragraph()
    r = p.add_run(checksum)
    r.font.name = "Courier New"
    r.font.size = Pt(9)
    add_heading(doc, "Appendix C - Interpretation rule", 2)
    add_body(doc, "Throughout this report, 'simulated success' means a local method returned a successful simulation result. 'Synthetic confirmation' means the application constructed confirmation-like fields locally. Neither term means a blockchain accepted or finalized a transaction. Only a genuine receipt from the identified chain, reconciled to the intended state change, would support that conclusion.")

    props = doc.core_properties
    props.title = "Orvilo Execution Evidence Report"
    props.subject = "Sandbox execution evidence for policy and guardrail workflows"
    props.author = "Orvilo engineering team"
    props.keywords = "Orvilo, execution evidence, sandbox, simulation, guardrails, Base Sepolia"
    props.comments = "Generated from repository evidence; no genuine on-chain transactions claimed."
    doc.settings.element.append(OxmlElement("w:updateFields"))
    doc.settings.element[-1].set(qn("w:val"), "true")
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
