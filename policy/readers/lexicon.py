"""Typed lexicon and vocabulary mappings for Reader A."""
from __future__ import annotations

from typing import Any
from policy.sorts import Sort

# Comparators to operator and family
COMPARATORS: dict[str, str] = {
    "under": "lt",
    "below": "lt",
    "less than": "lt",
    "lower than": "lt",
    "<": "lt",
    "<=": "le",
    "at most": "le",
    "no more than": "le",
    "over": "gt",
    "above": "gt",
    "greater than": "gt",
    "more than": "gt",
    ">": "gt",
    ">=": "ge",
    "at least": "ge",
    "exactly": "eq",
    "equal to": "eq",
    "=": "eq",
    "==": "eq",
}


# State nouns mapping to state variable names
STATE_NOUNS: dict[str, str] = {
    "gas price": "gas",
    "gas": "gas",
    "fees": "gas",
    "fee": "gas",
    "balance": "balance",
    "funds": "balance",
    "trade": "trade",
    "transaction": "trade",
    "purchase": "trade",
    "swap": "trade",
    "daily": "spent_today",
    "per day": "spent_today",
}

# Unit symbols and names
UNITS: dict[str, Sort] = {
    "gwei": Sort.GWEI,
    "$": Sort.USD,
    "usd": Sort.USD,
    "dollar": Sort.USD,
    "dollars": Sort.USD,
    "%": Sort.RATIO,
    "percent": Sort.RATIO,
}

# Action verbs
ACTION_VERBS: set[str] = {
    "buy", "purchase", "swap", "sell", "send", "pay"
}

# Negation and prohibition tokens that flip a constraint
NEGATION_TOKENS: set[str] = {
    "never", "do not", "don't", "must not", "no more than", "cannot"
}

# Compound constraint phrases:
# NOTE on balance after trade:
# In an autonomous execution wallet, checking balance before a trade is useless because
# a large trade could leave the wallet completely drained. Therefore, natural language
# constraints like "never let my balance go under $500" or "do not go under 500 dollars balance"
# are formalized as balance - trade >= 500 (minimum balance remaining AFTER the trade executes).
COMPOUND_BALANCE_FLOOR_PHRASES: set[str] = {
    "go under",
    "drop below",
    "fall below",
    "leave under",
}
