"""Orchestration loop for policy verification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from policy.ast import Policy
from policy.compare import Finding, compare
from policy.coercions import CoercionOption
from policy.errors import Unreadable
from policy.hashing import policy_hash
from policy.onchain import params as onchain_params
from policy.readback import readback as generate_readback
from policy.readers.base import Reader
from policy.sanity import sanity
from policy.typecheck import resolve, typecheck

LogCallable = Callable[[str, dict[str, Any]], None]
AskUserCallable = Callable[[str, tuple[CoercionOption, ...]], str]


@dataclass(frozen=True)
class VerifiedPolicy:
    status: Literal["VERIFIED"] = "VERIFIED"
    policy: Policy = field(default_factory=Policy)
    readback: str = ""
    hash: str = ""
    onchain: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1
    independence: Literal["rule-llm", "llm-llm"] = "rule-llm"
    log: tuple[dict[str, Any], ...] = ()
    ignored_clauses: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class NeedsHumanReview:
    status: Literal["NEEDS_HUMAN_REVIEW"] = "NEEDS_HUMAN_REVIEW"
    last_counterexample: Finding | None = None
    attempts: int = 2
    independence: Literal["rule-llm", "llm-llm"] = "rule-llm"
    log: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Rejected:
    status: Literal["REJECTED"] = "REJECTED"
    reasons: tuple[str, ...] = ()
    log: tuple[dict[str, Any], ...] = ()


def _default_log(event: str, data: dict[str, Any]) -> None:
    pass


def verify_policy(
    text: str,
    reader_a: Reader,
    reader_b: Reader,
    ask_user: AskUserCallable,
    log: LogCallable | None = None,
    reader_a_fallback: Reader | None = None,
) -> VerifiedPolicy | NeedsHumanReview | Rejected:
    """Verify natural language policy through dual independent formalizations and Z3 equivalence proof."""
    events: list[dict[str, Any]] = []

    def emit(event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, **data}
        events.append(payload)
        if log:
            log(event, data)

    emit("start", {"text": text})

    # 1. Reader A (deterministic) or fallback to Tier 2 (LLM-LLM)
    independence: Literal["rule-llm", "llm-llm"] = "rule-llm"
    try:
        a = reader_a.read(text)
    except Unreadable as e_a:
        if reader_a_fallback is not None:
            try:
                a = reader_a_fallback.read(text)
                independence = "llm-llm"
                emit("tier2_fallback", {"reason": str(e_a), "independence": "llm-llm"})
            except Unreadable as e_fb:
                emit("rejected", {"reasons": [str(e_fb)]})
                return Rejected(reasons=(f"Unreadable by primary and fallback readers: {e_fb}",), log=tuple(events))
        else:
            emit("rejected", {"reasons": [str(e_a)]})
            return Rejected(reasons=(f"Instruction unreadable: {e_a}",), log=tuple(events))

    # 2. Reader B (LLM untrusted)
    try:
        b = reader_b.read(text)
    except Unreadable as e_b:
        emit("rejected", {"reasons": [f"Reader B failed initial parse: {e_b}"]})
        return Rejected(reasons=(f"Reader B failed parse: {e_b}",), log=tuple(events))

    resolved_choices: dict[str, str] = {}
    attempts = 1
    max_repairs = 2
    last_finding: Finding | None = None

    while True:
        # 3. Type-check both ASTs
        issues_a = typecheck(a)
        issues_b = typecheck(b)

        # Union issues by stable issue_id
        issues_by_id: dict[str, Any] = {}
        for iss in issues_a + issues_b:
            if iss.issue_id not in issues_by_id:
                issues_by_id[iss.issue_id] = iss

        # Check for unconfirmed assumed provenance that was not resolved
        for iss in issues_by_id.values():
            if iss.kind == "ASSUMED_PROVENANCE":
                reasons = (iss.message,)
                emit("rejected", {"reasons": reasons})
                return Rejected(reasons=reasons, log=tuple(events))

        # Ask user for sort mismatches (each distinct issue asked only once)
        for iss_id, iss in issues_by_id.items():
            if iss.kind == "SORT_MISMATCH" and iss.options:
                if iss_id in resolved_choices:
                    chosen_opt_id = resolved_choices[iss_id]
                else:
                    question = f"Clarification needed for condition ({iss_id}):"
                    chosen_opt_id = ask_user(question, iss.options)
                    resolved_choices[iss_id] = chosen_opt_id
                    emit("clarify", {"issue_id": iss_id, "chosen_option": chosen_opt_id})
                a = resolve(a, iss_id, chosen_opt_id)
                b = resolve(b, iss_id, chosen_opt_id)

        # Re-check for any remaining assumed provenance after resolution
        remaining_issues = typecheck(a) + typecheck(b)
        for iss in remaining_issues:
            if iss.kind == "ASSUMED_PROVENANCE":
                reasons = (f"Policy retained assumed provenance: {iss.message}",)
                emit("rejected", {"reasons": reasons})
                return Rejected(reasons=reasons, log=tuple(events))

        # 4. Compile and compare
        findings = compare(a, b)
        if not findings:
            # Equivalent! Move to sanity check
            break

        # Mismatch found
        last_finding = findings[0]
        emit("mismatch", {
            "attempt": attempts,
            "direction": last_finding.direction,
            "counterexample": last_finding.display_state(),
        })

        if attempts > max_repairs:
            # Exceeded repairs -> human review
            emit("needs_human_review", {
                "attempts": attempts,
                "last_counterexample": last_finding.display_state(),
            })
            return NeedsHumanReview(
                last_counterexample=last_finding,
                attempts=attempts,
                independence=independence,
                log=tuple(events),
            )

        # 5. Call reader_b with feedback
        attempts += 1
        emit("repair", {"attempt": attempts, "feedback": last_finding.display_state()})
        try:
            b = reader_b.read(text, feedback=last_finding)
        except Unreadable as e:
            emit("needs_human_review", {"attempts": attempts, "error": str(e)})
            return NeedsHumanReview(
                last_counterexample=last_finding,
                attempts=attempts,
                independence=independence,
                log=tuple(events),
            )

    # 6. Sanity check on verified AST
    sanity_problems = sanity(a)
    if sanity_problems:
        emit("rejected", {"reasons": sanity_problems})
        return Rejected(reasons=tuple(sanity_problems), log=tuple(events))

    # 7. Construct VerifiedPolicy
    rb = generate_readback(a)
    h = policy_hash(a)
    params = onchain_params(a)

    emit("verified", {"hash": h, "readback": rb, "attempts": attempts})

    ignored = getattr(reader_a, "last_ignored_clauses", []) or ()

    return VerifiedPolicy(
        policy=a,
        readback=rb,
        hash=h,
        onchain=params,
        attempts=attempts,
        independence=independence,
        log=tuple(events),
        ignored_clauses=tuple(ignored),
    )
