"""Deterministic Reader A using spaCy dependency parse and typed lexicon."""
from __future__ import annotations

from fractions import Fraction
import re
from typing import Any
import spacy

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.errors import Unreadable
from policy.readers.base import Reader
from policy.readers.lexicon import (
    ACTION_VERBS,
    COMPARATORS,
    COMPOUND_BALANCE_FLOOR_PHRASES,
    NEGATION_TOKENS,
    STATE_NOUNS,
    UNITS,
)
from policy.sorts import Sort, lookup_var

# Regex permitted ONLY for numeral and unit tokenization (never meaning)
NUMERAL_UNIT_RE = re.compile(r"^\$?(\d+(?:\.\d+)?)\s*(%|gwei|usd|dollars?|\$)?$", re.IGNORECASE)


def parse_numeral_unit(text: str) -> tuple[Fraction, Sort | None]:
    """Tokenize numeral and unit symbol (e.g. '5%', '$500', '20gwei', '20')."""
    clean = text.strip()
    m = NUMERAL_UNIT_RE.match(clean)
    if not m:
        raise ValueError(f"Cannot parse numeral/unit from token: {text!r}")
    num_str, unit_str = m.group(1), m.group(2)
    val = Fraction(num_str)
    if not unit_str:
        if clean.startswith("$"):
            return val, Sort.USD
        return val, None

    u = unit_str.lower()
    if u in ("%", "percent"):
        return val / 100, Sort.RATIO
    elif u == "gwei":
        return val, Sort.GWEI
    elif u in ("$", "usd", "dollar", "dollars"):
        return val, Sort.USD
    return val, None


def classify_ignored_clause(clause_text: str) -> dict[str, str]:
    """Classify why a natural language clause was filtered out from formal policy verification."""
    clean = clause_text.strip()
    lower = clean.lower()

    jailbreak_keywords = [
        "risk", "care", "ignore", "bypass", "override", "disregard",
        "jailbreak", "no matter", "whatever", "force", "hack", "yolo",
        "all in", "drain", "forget", "unlimited", "don't care", "dont care"
    ]
    if any(k in lower for k in jailbreak_keywords):
        return {
            "clause": clean,
            "type": "JAILBREAK_ATTEMPT",
            "category": "Jailbreak / Safety-Override Blocked",
            "reason": (
                f"Prompt injection / safety override attempt detected ('{clean}'). "
                f"The Verified Policy Engine strictly refuses natural language override of safety invariants. "
                f"Mathematical solvency bounds and Z3 invariants remain deterministically enforced."
            ),
            "severity": "danger",
        }

    action_keywords = ["buy", "sell", "trade", "swap", "dump", "pump", "send", "spend", "execute", "order"]
    if any(k in lower for k in action_keywords):
        return {
            "clause": clean,
            "type": "UNCONSTRAINED_ACTION",
            "category": "Unconstrained Action Directive Ignored",
            "reason": (
                f"Action command ('{clean}') lacks verifiable mathematical thresholds, state variables, or risk boundaries."
            ),
            "severity": "warning",
        }

    return {
        "clause": clean,
        "type": "CONVERSATIONAL_FILLER",
        "category": "Conversational Text Ignored",
        "reason": (
            f"Phrase ('{clean}') contains no formal state variables (gas, balance, trade) or mathematical policy constraints."
        ),
        "severity": "info",
    }


class RuleReader(Reader):
    """Deterministic Reader A: uses spaCy dependency parser + typed lexicon."""

    def __init__(self, model_name: str = "en_core_web_sm"):
        try:
            self.nlp = spacy.load(model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load spaCy model {model_name!r}: {e}") from e
        self.last_ignored_clauses: list[dict[str, str]] = []

    def read(self, text: str, feedback: Any = None) -> Policy:
        text_clean = text.strip()
        if not text_clean:
            raise Unreadable("Empty input", raw_text=text)

        # Check for token allowlist special case: "Only trade WETH and USDC."
        doc = self.nlp(text_clean)
        tokens_lower = [t.text.lower() for t in doc]

        # 1. Allowlist rule: "Only trade WETH and USDC"
        if "only" in tokens_lower and "trade" in tokens_lower:
            tokens_found = []
            for t in doc:
                # Symbols like WETH, USDC, ETH, etc.
                if t.text.isupper() and len(t.text) >= 2 and t.text not in ("ETH", "USD"):
                    tokens_found.append(t.text)
                elif t.text in ("WETH", "USDC", "WBTC", "DAI"):
                    tokens_found.append(t.text)
            if tokens_found:
                return Policy(
                    action="swap_buy",
                    allow_tokens=tuple(tokens_found),
                )

        # 2. Approval threshold rule: "Ask me before anything over 500 dollars."
        if "ask" in tokens_lower and ("over" in tokens_lower or "above" in tokens_lower):
            # Find the numeral
            const_found = None
            for i, t in enumerate(doc):
                if t.like_num or NUMERAL_UNIT_RE.match(t.text):
                    # Check next token for unit
                    unit_text = doc[i + 1].text if i + 1 < len(doc) else ""
                    try:
                        val, s = parse_numeral_unit(f"{t.text} {unit_text}")
                        const_found = Const(val, s or Sort.USD)
                        break
                    except ValueError:
                        continue
            if const_found is not None:
                return Policy(
                    action="swap_buy",
                    approval_above_usd=const_found,
                )

        # Split clauses by "and" or punctuation if coordinating conjunction joins clauses
        clauses = self._split_clauses(text_clean)

        self.last_ignored_clauses = []
        triggers: list[Cmp] = []
        invariants: list[Cmp] = []
        for clause in clauses:
            trig, inv = self._parse_clause(clause)
            if trig is not None:
                triggers.append(trig)
            if inv is not None:
                invariants.append(inv)
            if trig is None and inv is None:
                self.last_ignored_clauses.append(classify_ignored_clause(clause))

        if not triggers and not invariants:
            raise Unreadable(f"No valid policy rules recognized in instruction: {text!r}", raw_text=text)

        return Policy(
            action="swap_buy",
            triggers=tuple(triggers),
            invariants=tuple(invariants),
        )

    def _split_clauses(self, text: str) -> list[str]:
        # Split on sentence boundaries or coordinating conjunctions
        parts = re.split(r"\.\s+|\;\s+|,?\s+and\s+", text)
        return [p.strip().rstrip(".") for p in parts if p.strip().rstrip(".")]

    def _parse_clause(self, clause_text: str) -> tuple[Cmp | None, Cmp | None]:
        doc = self.nlp(clause_text)
        lower_text = clause_text.lower()

        # Check for compound balance floor: "never let my balance go under 500 dollars",
        # "do not go under 500 dollars balance", or readback "keep the balance after each trade at least $500"
        is_negated = any(neg in lower_text for neg in NEGATION_TOKENS)
        is_balance_floor = any(phrase in lower_text for phrase in COMPOUND_BALANCE_FLOOR_PHRASES) or (
            "balance" in lower_text and ("under" in lower_text or "below" in lower_text or "after" in lower_text)
        )

        if is_balance_floor:
            # Extract numeral & unit
            const_node = self._extract_const(doc, expected_sort=Sort.USD)
            if const_node is not None:
                # Map to balance - trade >= X
                cmp_node = Cmp(
                    op="ge",
                    lhs=BinOp("sub", Var("balance"), Var("trade")),
                    rhs=const_node,
                )
                return None, cmp_node

        # Check for per-tx cap: "Don't spend more than 300 dollars in one transaction"
        if ("one transaction" in lower_text or "single transaction" in lower_text or "per trade" in lower_text) and (
            "spend" in lower_text or "trade" in lower_text
        ):
            const_node = self._extract_const(doc, expected_sort=Sort.USD)
            if const_node is not None:
                return None, Cmp(op="le", lhs=Var("trade"), rhs=const_node)

        # Check for daily cap: "No more than 1000 dollars per day in total"
        if "per day" in lower_text or "daily" in lower_text:
            const_node = self._extract_const(doc, expected_sort=Sort.USD)
            if const_node is not None:
                # spent_today + trade <= X
                lhs = BinOp("add", Var("spent_today"), Var("trade"))
                return None, Cmp(op="le", lhs=lhs, rhs=const_node)

        # Standard clause: noun + comparator + constant
        var_name = self._find_state_var(doc)
        cmp_op = self._find_comparator(doc)
        const_node = self._extract_const(doc, expected_sort=lookup_var(var_name).sort if var_name else None)

        if var_name is not None and cmp_op is not None and const_node is not None:
            # Check if this clause is a trigger or invariant
            is_trigger = "when" in lower_text or "if" in lower_text or var_name in ("gas", "avg24h", "pctile24h")
            # For triggers like "when gas is under 20 gwei", under maps to "le"
            if is_trigger and cmp_op == "lt":
                cmp_op = "le"

            cmp_obj = Cmp(op=cmp_op, lhs=Var(var_name), rhs=const_node)
            if is_trigger:
                return cmp_obj, None
            else:
                return None, cmp_obj

        # If this clause has no numerals or recognized state variables, treat as non-constraint conversational text
        if const_node is None and var_name is None:
            return None, None

        # If we couldn't parse this clause into a valid constraint, raise Unreadable
        raise Unreadable(f"Cannot parse clause into policy constraint: {clause_text!r}", raw_text=clause_text)

    def _find_state_var(self, doc) -> str | None:
        text = doc.text.lower()
        if "gas price" in text:
            return "gas"
        for t in doc:
            lemma = t.lemma_.lower()
            if lemma in STATE_NOUNS:
                return STATE_NOUNS[lemma]
            if t.text.lower() in STATE_NOUNS:
                return STATE_NOUNS[t.text.lower()]
        return None

    def _find_comparator(self, doc) -> str | None:
        text = doc.text.lower()
        # Multi-word comparators first
        for phrase in ("no more than", "at most", "less than", "greater than", "at least", "more than"):
            if phrase in text:
                return COMPARATORS[phrase]
        for t in doc:
            w = t.text.lower()
            if w in COMPARATORS:
                return COMPARATORS[w]
        return None

    def _extract_const(self, doc, expected_sort: Sort | None = None) -> Const | None:
        # Find numeric token
        for i, t in enumerate(doc):
            # Check combined token like "20gwei", "5%", "$500"
            try:
                val, s = parse_numeral_unit(t.text)
                # Check if next token has unit e.g. "20" then "gwei" or "dollars"
                if s is None and i + 1 < len(doc):
                    next_w = doc[i + 1].text.lower()
                    if next_w in UNITS:
                        s = UNITS[next_w]
                        if s == Sort.RATIO:
                            val = val / 100

                # Check previous token for '$'
                if s is None and i > 0 and doc[i - 1].text == "$":
                    s = Sort.USD

                if s is None:
                    # Bare constant adopting expected sort
                    if expected_sort is not None:
                        return Const(value=val, sort=expected_sort, unit_inferred=True)
                    return None
                return Const(value=val, sort=s, unit_inferred=False)
            except ValueError:
                continue
        return None
