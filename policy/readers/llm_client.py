"""LLM Client protocol and environment-configurable adapter."""
from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@runtime_checkable
class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Request structured JSON completion adhering to the provided JSON Schema."""
        ...


class EnvLLMClient:
    """Production LLM adapter driven by environment variables (LLM_PROVIDER, LLM_API_KEY)."""
    def __init__(self, provider: str | None = None, api_key: str | None = None, model: str | None = None):
        self.provider = (provider or os.environ.get("LLM_PROVIDER", "mock")).lower()
        self.api_key = (
            api_key
            or os.environ.get("LLM_API_KEY")
            or os.environ.get(f"{self.provider.upper()}_API_KEY", "")
            or os.environ.get("GROQ_API_KEY", "")
        )
        self.model = model or os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self.provider == "mock":
            raise RuntimeError("EnvLLMClient configured with provider 'mock'; use MockLLMClient for testing.")

        if self.provider == "groq":
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not set in environment.")
            import requests
            url = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "WalletAgent/1.0",
            }
            import time
            schema_guide = (
                "Output JSON conforming to:\n"
                "{\n"
                '  "node": "Policy",\n'
                '  "action": "swap_buy",\n'
                '  "triggers": [{"node": "Cmp", "op": "le"|"lt"|"ge"|"gt", "lhs": {"node": "Var", "name": "gas"}, "rhs": {"node": "Const", "value": "num_or_fraction", "sort": "GWEI"}}],\n'
                '  "invariants": [\n'
                '    {"node": "Cmp", "op": "ge"|"le", "lhs": {"node": "BinOp", "op": "sub", "lhs": {"node": "Var", "name": "balance"}, "rhs": {"node": "Var", "name": "trade"}}, "rhs": {"node": "Const", "value": "num", "sort": "USD"}},\n'
                '    {"node": "Cmp", "op": "le", "lhs": {"node": "Var", "name": "trade"}, "rhs": {"node": "Const", "value": "num", "sort": "USD"}}\n'
                "  ]\n"
                "}\n"
                "Notes: For gas 'under X', op is 'le'. For balance floor 'never let balance drop below X', invariant is 'balance - trade >= X' with lhs BinOp sub."
            )
            system_instruction = f"{system}\n\n{schema_guide}"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            last_err = ""
            for attempt in range(4):
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 429:
                    time.sleep(3.5 * (attempt + 1))
                    continue
                if resp.status_code != 200:
                    last_err = resp.text
                    time.sleep(1.0)
                    continue
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
            raise RuntimeError(f"Groq API error after retries: {last_err}")

        # Network integration hook for external providers if configured
        raise NotImplementedError(f"Provider {self.provider!r} not configured with live API client.")
