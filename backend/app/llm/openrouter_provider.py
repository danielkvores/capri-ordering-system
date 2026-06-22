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


class OpenRouterProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def extract_actions(self, user_text: str, session: SessionState) -> LLMResult:
        started = time.perf_counter()
        errors: list[str] = []

        if not self.settings.openrouter_api_key:
            return LLMResult(
                raw=None,
                action=None,
                latency_ms=0,
                errors=["OPENROUTER_API_KEY is not configured."],
            )
        if not self.settings.openrouter_model:
            return LLMResult(
                raw=None,
                action=None,
                latency_ms=0,
                errors=["OPENROUTER_MODEL is not configured."],
            )

        raw = await self._chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": extraction_user_prompt(user_text, session)},
            ]
        )
        parsed, error = parse_action(raw)
        if parsed:
            return LLMResult(raw=raw, action=parsed, latency_ms=elapsed_ms(started), errors=errors)

        errors.append(error or "Unknown JSON parse error.")
        repaired_raw = await self._chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt(raw, errors[-1])},
            ]
        )
        parsed, repair_error = parse_action(repaired_raw)
        if parsed:
            return LLMResult(raw=repaired_raw, action=parsed, latency_ms=elapsed_ms(started), errors=errors)

        errors.append(repair_error or "JSON repair failed.")
        return LLMResult(raw=repaired_raw, action=None, latency_ms=elapsed_ms(started), errors=errors)

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }
        payload: dict[str, Any] = {
            "model": self.settings.openrouter_model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


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
