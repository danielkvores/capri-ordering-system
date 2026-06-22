import json

from app.menu import menu_for_prompt
from app.schemas import SessionState


ACTION_SCHEMA_DESCRIPTION = {
    "reasoning_summary": "short summary of understood customer intent",
    "language": "hu",
    "confidence": 0.0,
    "customer_updates": {"name": None, "phone": None},
    "fulfilment_updates": {"type": None, "address_text": None, "pickup_time": None},
    "payment_method": None,
    "cart_actions": [
        {
            "operation": "add_item",
            "item_query": "customer words for item",
            "menu_item_id": None,
            "quantity": 1,
            "size": None,
            "extra_toppings": [],
            "removed_ingredients": [],
            "notes": "",
        }
    ],
    "clarification": {"needed": False, "question_hu": None, "reason": None},
    "suggested_assistant_response_hu": "short Hungarian response",
}


SYSTEM_PROMPT = """You are a Hungarian-speaking restaurant dispatcher for an Italian/pizza restaurant.
Your only task is to extract structured JSON actions from the latest Hungarian customer message.

Rules:
- Return one valid JSON object only. No Markdown. No prose outside JSON.
- Use Hungarian in suggested_assistant_response_hu and clarification.question_hu.
- Do not invent menu items, prices, addresses, opening hours, or customer profile data.
- Prefer menu_item_id only when the customer clearly asked for a listed menu item.
- If uncertain, leave IDs null and set clarification.needed when needed.
- The backend owns the order state. You only propose actions.
- Never claim an order is confirmed.
- Payment method must be "cash", "card", or null.
- Fulfilment type must be "delivery", "pickup", or null.
- For pizza size use "32cm", "45cm", or null.
- Extract phone numbers as written; the backend will normalize them.
- Extract multiple cart items when present in one message.
- If the customer says "amint lehet" or similar for pickup time, use "as soon as possible".
- Do not include private chain-of-thought; reasoning_summary must be brief.
"""


def extraction_user_prompt(user_text: str, session: SessionState) -> str:
    return json.dumps(
        {
            "task": "Extract proposed order actions from latest_user_message.",
            "output_shape": ACTION_SCHEMA_DESCRIPTION,
            "current_session_state": session.model_dump(mode="json"),
            "menu": menu_for_prompt(),
            "latest_user_message": user_text,
        },
        ensure_ascii=False,
    )


def repair_prompt(raw_response: str, error: str) -> str:
    return json.dumps(
        {
            "task": "Repair this model response into one valid JSON object matching the expected action schema.",
            "expected_shape": ACTION_SCHEMA_DESCRIPTION,
            "parse_error": error,
            "raw_response": raw_response,
        },
        ensure_ascii=False,
    )
