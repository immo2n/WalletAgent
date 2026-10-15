"""JSON Schema for validating typed policy AST dictionaries."""
from __future__ import annotations

from typing import Any
import jsonschema

from policy.errors import Unreadable

TERM_SCHEMA: dict[str, Any] = {
    "$id": "#/definitions/term",
    "oneOf": [
        {
            "type": "object",
            "properties": {
                "node": {"const": "Const"},
                "value": {"type": "string"},
                "sort": {
                    "type": "string",
                    "enum": ["GWEI", "USD", "RATIO", "TOKEN", "ADDRESS", "TIME", "COUNT", "BOOL"],
                },
                "unit_inferred": {"type": "boolean"},
            },
            "required": ["node", "value", "sort"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "node": {"const": "Var"},
                "name": {"type": "string", "enum": ["gas", "avg24h", "pctile24h", "balance", "trade", "spent_today"]},
            },
            "required": ["node", "name"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "node": {"const": "BinOp"},
                "op": {"type": "string", "enum": ["mul", "sub", "add"]},
                "lhs": {"$ref": "#/definitions/term"},
                "rhs": {"$ref": "#/definitions/term"},
            },
            "required": ["node", "op", "lhs", "rhs"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "node": {"const": "Coerced"},
                "inner": {"$ref": "#/definitions/term"},
                "coercion_id": {"type": "string"},
                "provenance": {"type": "string", "enum": ["confirmed", "assumed"]},
            },
            "required": ["node", "inner", "coercion_id", "provenance"],
            "additionalProperties": False,
        },
    ],
}

CMP_SCHEMA: dict[str, Any] = {
    "$id": "#/definitions/cmp",
    "type": "object",
    "properties": {
        "node": {"const": "Cmp"},
        "op": {"type": "string", "enum": ["lt", "le", "gt", "ge", "eq"]},
        "lhs": {"$ref": "#/definitions/term"},
        "rhs": {"$ref": "#/definitions/term"},
    },
    "required": ["node", "op", "lhs", "rhs"],
    "additionalProperties": False,
}

POLICY_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "definitions": {
        "term": TERM_SCHEMA,
        "cmp": CMP_SCHEMA,
    },
    "properties": {
        "node": {"const": "Policy"},
        "action": {"type": "string"},
        "triggers": {
            "type": "array",
            "items": {"$ref": "#/definitions/cmp"},
        },
        "invariants": {
            "type": "array",
            "items": {"$ref": "#/definitions/cmp"},
        },
        "allow_tokens": {
            "type": "array",
            "items": {"type": "string"},
        },
        "allow_routers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "allow_recipients": {
            "type": "array",
            "items": {"type": "string"},
        },
        "approval_above_usd": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "node": {"const": "Const"},
                        "value": {"type": "string"},
                        "sort": {"const": "USD"},
                        "unit_inferred": {"type": "boolean"},
                    },
                    "required": ["node", "value", "sort"],
                    "additionalProperties": False,
                },
            ]
        },
    },
    "required": ["action", "triggers", "invariants"],
    "additionalProperties": False,
}


def validate_policy_json(data: dict[str, Any]) -> None:
    """Validate JSON dictionary against the AST JSON schema. Raises Unreadable on failure."""
    try:
        jsonschema.validate(instance=data, schema=POLICY_SCHEMA)
    except jsonschema.ValidationError as err:
        raise Unreadable(f"JSON does not conform to Policy schema: {err.message}") from err
