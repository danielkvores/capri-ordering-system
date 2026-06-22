from dataclasses import dataclass
from typing import Protocol

from app.schemas import LLMAction, SessionState


@dataclass
class LLMResult:
    raw: str | None
    action: LLMAction | None
    latency_ms: int
    errors: list[str]


class LLMProvider(Protocol):
    async def extract_actions(self, user_text: str, session: SessionState) -> LLMResult:
        ...
