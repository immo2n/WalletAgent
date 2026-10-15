"""Typed AST dataclasses for the policy language."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal, Union

from policy.sorts import REGISTRY, Sort


def parse_fraction(val: Any) -> Fraction:
    """Safely parse Fraction from str (e.g. '0.05', '5', '1/20', '5/1'), int, or Fraction."""
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val, 1)
    if isinstance(val, float):
        # We avoid floats in policy math, but if passed stringify accurately
        return Fraction(str(val))
    if isinstance(val, str):
        val = val.strip()
        if "/" in val:
            parts = val.split("/", 1)
            return Fraction(int(parts[0].strip()), int(parts[1].strip()))
        return Fraction(val)
    raise TypeError(f"Cannot parse Fraction from {type(val)}: {val!r}")


def format_fraction(f: Fraction) -> str:
    """Format Fraction canonically as 'n/d' string."""
    return f"{f.numerator}/{f.denominator}"


@dataclass(frozen=True)
class Const:
    value: Fraction
    sort: Sort
    unit_inferred: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.value, Fraction):
            object.__setattr__(self, "value", parse_fraction(self.value))
        if not isinstance(self.sort, Sort):
            object.__setattr__(self, "sort", Sort(self.sort))

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "Const",
            "value": format_fraction(self.value),
            "sort": self.sort.value,
            "unit_inferred": self.unit_inferred,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Const:
        return cls(
            value=parse_fraction(data["value"]),
            sort=Sort(data["sort"]),
            unit_inferred=bool(data.get("unit_inferred", False)),
        )


@dataclass(frozen=True)
class Var:
    name: str

    def __post_init__(self) -> None:
        if self.name not in REGISTRY:
            raise ValueError(f"Unknown state variable: {self.name!r}. Allowed: {list(REGISTRY.keys())}")

    @property
    def sort(self) -> Sort:
        return REGISTRY[self.name].sort

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "Var",
            "name": self.name,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Var:
        return cls(name=data["name"])


BinOpCode = Literal["mul", "sub", "add"]
CmpOpCode = Literal["lt", "le", "gt", "ge", "eq"]


@dataclass(frozen=True)
class BinOp:
    op: BinOpCode
    lhs: Term
    rhs: Term

    def __post_init__(self) -> None:
        if self.op not in ("mul", "sub", "add"):
            raise ValueError(f"Unsupported BinOp operator: {self.op}")

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "BinOp",
            "op": self.op,
            "lhs": self.lhs.to_json(),
            "rhs": self.rhs.to_json(),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BinOp:
        return cls(
            op=data["op"],
            lhs=ast_from_json(data["lhs"]),
            rhs=ast_from_json(data["rhs"]),
        )


@dataclass(frozen=True)
class Coerced:
    inner: Term
    coercion_id: str
    provenance: Literal["confirmed", "assumed"]

    def __post_init__(self) -> None:
        if self.provenance not in ("confirmed", "assumed"):
            raise ValueError(f"Invalid provenance: {self.provenance}")

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "Coerced",
            "inner": self.inner.to_json(),
            "coercion_id": self.coercion_id,
            "provenance": self.provenance,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Coerced:
        return cls(
            inner=ast_from_json(data["inner"]),
            coercion_id=data["coercion_id"],
            provenance=data["provenance"],
        )


Term = Union[Const, Var, BinOp, Coerced]


@dataclass(frozen=True)
class Cmp:
    op: CmpOpCode
    lhs: Term
    rhs: Term

    def __post_init__(self) -> None:
        if self.op not in ("lt", "le", "gt", "ge", "eq"):
            raise ValueError(f"Unsupported Cmp operator: {self.op}")

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "Cmp",
            "op": self.op,
            "lhs": self.lhs.to_json(),
            "rhs": self.rhs.to_json(),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Cmp:
        return cls(
            op=data["op"],
            lhs=ast_from_json(data["lhs"]),
            rhs=ast_from_json(data["rhs"]),
        )


@dataclass(frozen=True)
class Policy:
    action: str = "swap_buy"
    triggers: tuple[Cmp, ...] = ()
    invariants: tuple[Cmp, ...] = ()
    allow_tokens: tuple[str, ...] = ()
    allow_routers: tuple[str, ...] = ()
    allow_recipients: tuple[str, ...] = ()
    approval_above_usd: Const | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "triggers", tuple(self.triggers))
        object.__setattr__(self, "invariants", tuple(self.invariants))
        object.__setattr__(self, "allow_tokens", tuple(self.allow_tokens))
        object.__setattr__(self, "allow_routers", tuple(self.allow_routers))
        object.__setattr__(self, "allow_recipients", tuple(self.allow_recipients))
        if self.approval_above_usd is not None and not isinstance(self.approval_above_usd, Const):
            raise TypeError("approval_above_usd must be a Const or None")

    def to_json(self) -> dict[str, Any]:
        return {
            "node": "Policy",
            "action": self.action,
            "triggers": [t.to_json() for t in self.triggers],
            "invariants": [inv.to_json() for inv in self.invariants],
            "allow_tokens": list(self.allow_tokens),
            "allow_routers": list(self.allow_routers),
            "allow_recipients": list(self.allow_recipients),
            "approval_above_usd": self.approval_above_usd.to_json() if self.approval_above_usd else None,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Policy:
        approval = data.get("approval_above_usd")
        return cls(
            action=data.get("action", "swap_buy"),
            triggers=tuple(Cmp.from_json(t) for t in data.get("triggers", [])),
            invariants=tuple(Cmp.from_json(inv) for inv in data.get("invariants", [])),
            allow_tokens=tuple(data.get("allow_tokens", [])),
            allow_routers=tuple(data.get("allow_routers", [])),
            allow_recipients=tuple(data.get("allow_recipients", [])),
            approval_above_usd=Const.from_json(approval) if approval else None,
        )


def ast_from_json(data: dict[str, Any]) -> Any:
    node_type = data.get("node")
    if node_type == "Const":
        return Const.from_json(data)
    elif node_type == "Var":
        return Var.from_json(data)
    elif node_type == "BinOp":
        return BinOp.from_json(data)
    elif node_type == "Coerced":
        return Coerced.from_json(data)
    elif node_type == "Cmp":
        return Cmp.from_json(data)
    elif node_type == "Policy":
        return Policy.from_json(data)
    raise ValueError(f"Unrecognized node type in json: {node_type!r}")
