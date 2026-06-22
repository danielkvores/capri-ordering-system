import re
import time

from app.llm.base import LLMResult
from app.menu import match_menu_candidates, normalize_text
from app.schemas import CartAction, CustomerUpdates, FulfilmentUpdates, LLMAction, SessionState


class MockProvider:
    async def extract_actions(self, user_text: str, session: SessionState) -> LLMResult:
        started = time.perf_counter()
        text = normalize_text(user_text)
        raw_phone = re.search(r"(\+?\d[\d\s\-/()]{7,}\d)", user_text)

        action = LLMAction(
            reasoning_summary="Development mock extraction.",
            confidence=0.4,
            customer_updates=CustomerUpdates(phone=raw_phone.group(1) if raw_phone else None),
            fulfilment_updates=FulfilmentUpdates(
                type=detect_fulfilment(text),
                address_text=user_text if any(word in text for word in ["utca", "ter", "korut", "ut"]) else None,
                pickup_time=detect_pickup_time(text),
            ),
            payment_method=detect_payment(text),
            cart_actions=detect_cart_actions(user_text, text),
        )
        return LLMResult(
            raw=action.model_dump_json(),
            action=action,
            latency_ms=int((time.perf_counter() - started) * 1000),
            errors=[],
        )


def detect_fulfilment(text: str) -> str | None:
    if "hazhoz" in text or "kiszallit" in text:
        return "delivery"
    if "elvitel" in text or "atvetel" in text:
        return "pickup"
    return None


def detect_pickup_time(text: str) -> str | None:
    if "amint lehet" in text or "minel hamarabb" in text:
        return "as soon as possible"
    match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return None


def detect_payment(text: str) -> str | None:
    if "keszpen" in text:
        return "cash"
    if "kartya" in text:
        return "card"
    return None


def detect_cart_actions(user_text: str, normalized_text: str) -> list[CartAction]:
    actions: list[CartAction] = []
    for candidate in match_menu_candidates(user_text):
        quantity = 1
        if any(word in normalized_text for word in ["ket ", "ketto", "kettot", "2 "]):
            quantity = 2
        elif any(word in normalized_text for word in ["harom", "3 "]):
            quantity = 3
        size = detect_size(normalized_text)
        extras = ["extra sajt"] if "extra sajt" in normalized_text else []
        actions.append(
            CartAction(
                operation="add_item",
                item_query=candidate.name_hu,
                menu_item_id=candidate.id,
                quantity=quantity,
                size=size,
                extra_toppings=extras,
            )
        )
        break
    return actions


def detect_size(text: str) -> str | None:
    if re.search(r"\b45\s*(cm|centi|os)\b", text):
        return "45cm"
    if re.search(r"\b32\s*(cm|centi|es)\b", text):
        return "32cm"
    return None
