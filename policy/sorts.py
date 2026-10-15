"""Sort definitions, registry, and canonical units for the policy language."""
from __future__ import annotations

from enum import Enum
from fractions import Fraction
from typing import NamedTuple


class Sort(str, Enum):
    GWEI = "GWEI"
    USD = "USD"
    RATIO = "RATIO"
    TOKEN = "TOKEN"
    ADDRESS = "ADDRESS"
    TIME = "TIME"
    COUNT = "COUNT"
    BOOL = "BOOL"

    def __str__(self) -> str:
        return self.value


class VarMeta(NamedTuple):
    sort: Sort
    canonical_unit: str
    doc: str


# Fixed registry of known state variables
REGISTRY: dict[str, VarMeta] = {
    "gas": VarMeta(Sort.GWEI, "gwei", "Current transaction gas price"),
    "avg24h": VarMeta(Sort.GWEI, "gwei", "24-hour moving average gas price"),
    "pctile24h": VarMeta(Sort.RATIO, "%", "Gas percentile rank in the last 24 hours (0.0 to 1.0)"),
    "balance": VarMeta(Sort.USD, "USD", "Current wallet balance in USD"),
    "trade": VarMeta(Sort.USD, "USD", "Proposed transaction / trade amount in USD"),
    "spent_today": VarMeta(Sort.USD, "USD", "Cumulative USD spent today so far"),
}

# Canonical units mapping for Sorts
CANONICAL_UNITS: dict[Sort, str] = {
    Sort.GWEI: "gwei",
    Sort.USD: "USD",
    Sort.RATIO: "%",
}


def lookup_var(name: str) -> VarMeta | None:
    return REGISTRY.get(name)
