import json
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.llm.base import LLMResult
from app.llm.prompts import SYSTEM_PROMPT, extraction_user_prompt, repair_prompt
from app.schemas import LLMAction, SessionState


ACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reasoning_summary": {"type": ["string", "null"]},
        "language": {"type": "string"},
        "confidence": {"type": "number"},
        "customer_updates": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
            },
            "required": ["name", "phone"],
            "additionalProperties": False,
        },
        "fulfilment_updates": {
            "type": "object",
            "properties": {
                "type": {"type": ["string", "null"]},
                "address_text": {"type": ["string", "null"]},
                "pickup_time": {"type": ["string", "null"]},
            },
            "required": ["type", "address_text", "pickup_time"],
            "additionalProperties": False,
        },
        "payment_method": {"type": ["string", "null"]},
        "cart_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "item_query": {"type": ["string", "null"]},
                    "menu_item_id": {"type": ["string", "null"]},
                    "quantity": {"type": "integer"},
                    "size": {"type": ["string", "null"]},
                    "extra_toppings": {"type": "array", "items": {"type": "string"}},
                    "removed_ingredients": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": [
                    "operation",
                    "item_query",
                    "menu_item_id",
                    "quantity",
                    "size",
                    "extra_toppings",
                    "removed_ingredients",
                    "notes",
                ],
                "additionalProperties": False,
            },
        },
        "clarification": {
            "type": "object",
            "properties": {
                "needed": {"type": "boolean"},
                "question_hu": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
            },
            "required": ["needed", "question_hu", "reason"],
            "additionalProperties": False,
        },
        "suggested_assistant_response_hu": {"type": ["string", "null"]},
    },
    "required": [
        "reasoning_summary",
        "language",
        "confidence",
        "customer_updates",
        "fulfilment_updates",
        "payment_method",
        "cart_actions",
        "clarification",
        "suggested_assistant_response_hu",
    ],
    "additionalProperties": False,
}


class CerebrasProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def extract_actions(self, user_text: str, session: SessionState) -> LLMResult:
        started = time.perf_counter()
        errors: list[str] = []

        if not self.settings.cerebras_api_key_configured:
            return LLMResult(
                raw=None,
                action=None,
                latency_ms=0,
                errors=["CEREBRAS_API_KEY is not configured."],
            )

        raw = await self._chat(
            [
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": extraction_user_prompt(user_text, session)},
            ],
            strict_schema=True,
        )
        parsed, error = parse_action(raw)
        if parsed:
            return LLMResult(raw=raw, action=parsed, latency_ms=elapsed_ms(started), errors=errors)

        errors.append(error or "Unknown JSON parse error.")
        repaired_raw = await self._chat(
            [
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt(raw, errors[-1])},
            ],
            strict_schema=False,
        )
        parsed, repair_error = parse_action(repaired_raw)
        if parsed:
            return LLMResult(raw=repaired_raw, action=parsed, latency_ms=elapsed_ms(started), errors=errors)

        errors.append(repair_error or "JSON repair failed.")
        return LLMResult(raw=repaired_raw, action=None, latency_ms=elapsed_ms(started), errors=errors)

    async def _chat(self, messages: list[dict[str, str]], strict_schema: bool) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.cerebras_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.settings.cerebras_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1200,
            "response_format": self._response_format(strict_schema),
        }
        url = f"{self.settings.cerebras_base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.is_error:
                raise RuntimeError(f"Cerebras returned {response.status_code}: {response.text}")
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _response_format(self, strict_schema: bool) -> dict[str, Any]:
        if not strict_schema:
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "restaurant_order_action",
                "strict": True,
                "schema": ACTION_JSON_SCHEMA,
            },
        }


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def parse_action(raw: str) -> tuple[LLMAction | None, str | None]:
    try:
        return LLMAction.model_validate(json.loads(extract_json_object(raw))), None
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return None, str(exc)


def extract_json_object(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in response.")
    return match.group(0)
