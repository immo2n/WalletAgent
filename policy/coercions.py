"""Coercion table and rewrite logic for resolving sort mismatches."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Term, Var
from policy.sorts import Sort


@dataclass(frozen=True)
class CoercionOption:
    id: str
    description: str
    target_sort: Sort
    # Rewrite function: takes (cmp_op, var_name, const_val) -> Cmp
    builder: Callable[[str, str, Fraction], Cmp]


def _format_ratio_pct(r: Fraction) -> str:
    pct = r * 100
    if pct.denominator == 1:
        return f"{pct.numerator}%"
    return f"{float(pct):.2f}%"


def _format_ratio_numeral(r: Fraction) -> str:
    num = r * 100
    if num.denominator == 1:
        return str(num.numerator)
    return f"{float(num):.2f}"


# -----------------------------------------------------------------------------
# Builders for (GWEI, RATIO)
# -----------------------------------------------------------------------------
def _build_pct_below_avg24h(op: str, var_name: str, r: Fraction) -> Cmp:
    # gas <= avg24h * (1 - r)
    # op is normalized to le
    factor = BinOp("sub", Const(Fraction(1, 1), Sort.RATIO), Const(r, Sort.RATIO))
    rhs_term = BinOp("mul", Var("avg24h"), factor)
    coerced_rhs = Coerced(inner=rhs_term, coercion_id="pct_below_avg24h", provenance="confirmed")
    return Cmp(op="le", lhs=Var(var_name), rhs=coerced_rhs)


def _build_pct_above_avg24h(op: str, var_name: str, r: Fraction) -> Cmp:
    # gas >= avg24h * (1 + r)
    factor = BinOp("add", Const(Fraction(1, 1), Sort.RATIO), Const(r, Sort.RATIO))
    rhs_term = BinOp("mul", Var("avg24h"), factor)
    coerced_rhs = Coerced(inner=rhs_term, coercion_id="pct_above_avg24h", provenance="confirmed")
    return Cmp(op="ge", lhs=Var(var_name), rhs=coerced_rhs)


def _build_lowest_pctile24h(op: str, var_name: str, r: Fraction) -> Cmp:
    # pctile24h <= r
    coerced_rhs = Coerced(inner=Const(r, Sort.RATIO), coercion_id="lowest_pctile24h", provenance="confirmed")
    return Cmp(op="le", lhs=Var("pctile24h"), rhs=coerced_rhs)


def _build_absolute_reinterpret(op: str, var_name: str, r: Fraction) -> Cmp:
    # 5% becomes 5 gwei
    num_gwei = r * 100
    coerced_rhs = Coerced(inner=Const(num_gwei, Sort.GWEI), coercion_id="absolute_reinterpret", provenance="confirmed")
    return Cmp(op=op if op in ("lt", "le", "gt", "ge", "eq") else "le", lhs=Var(var_name), rhs=coerced_rhs)


# -----------------------------------------------------------------------------
# Builders for (USD, RATIO)
# -----------------------------------------------------------------------------
def _build_pct_of_balance(op: str, var_name: str, r: Fraction) -> Cmp:
    # trade <= balance * r
    rhs_term = BinOp("mul", Var("balance"), Const(r, Sort.RATIO))
    coerced_rhs = Coerced(inner=rhs_term, coercion_id="pct_of_balance", provenance="confirmed")
    return Cmp(op=op if op in ("lt", "le", "gt", "ge", "eq") else "le", lhs=Var(var_name), rhs=coerced_rhs)


@dataclass(frozen=True)
class CoercionEntry:
    id: str
    lhs_sort: Sort
    rhs_sort: Sort
    text_template: str
    builder: Callable[[str, str, Fraction], Cmp]


COERCION_TABLE: list[CoercionEntry] = [
    CoercionEntry(
        id="pct_below_avg24h",
        lhs_sort=Sort.GWEI,
        rhs_sort=Sort.RATIO,
        text_template="gas is at least {pct} below its 24h average",
        builder=_build_pct_below_avg24h,
    ),
    CoercionEntry(
        id="pct_above_avg24h",
        lhs_sort=Sort.GWEI,
        rhs_sort=Sort.RATIO,
        text_template="gas is at least {pct} above its 24h average",
        builder=_build_pct_above_avg24h,
    ),
    CoercionEntry(
        id="lowest_pctile24h",
        lhs_sort=Sort.GWEI,
        rhs_sort=Sort.RATIO,
        text_template="gas is within the lowest {pct} of the last 24h",
        builder=_build_lowest_pctile24h,
    ),
    CoercionEntry(
        id="absolute_reinterpret",
        lhs_sort=Sort.GWEI,
        rhs_sort=Sort.RATIO,
        text_template="{num} gwei, not a percentage",
        builder=_build_absolute_reinterpret,
    ),
    CoercionEntry(
        id="pct_of_balance",
        lhs_sort=Sort.USD,
        rhs_sort=Sort.RATIO,
        text_template="{pct} of current balance",
        builder=_build_pct_of_balance,
    ),
]


def find_coercion_options(lhs_sort: Sort, rhs_sort: Sort, const_val: Fraction) -> list[CoercionOption]:
    """Find all matching coercion options in the coercion table for (lhs_sort, rhs_sort)."""
    options: list[CoercionOption] = []
    pct_str = _format_ratio_pct(const_val)
    num_str = _format_ratio_numeral(const_val)

    for entry in COERCION_TABLE:
        if entry.lhs_sort == lhs_sort and entry.rhs_sort == rhs_sort:
            desc = entry.text_template.format(pct=pct_str, num=num_str)
            options.append(
                CoercionOption(
                    id=entry.id,
                    description=desc,
                    target_sort=entry.lhs_sort,
                    builder=entry.builder,
                )
            )
    return options
