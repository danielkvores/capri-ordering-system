import re
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.customers import find_customer_by_phone, normalize_phone
from app.menu import get_menu_item, load_menu, match_menu_candidates, normalize_text
from app.schemas import CartAction, CartItem, LLMAction, MenuItem, SessionState


HUNGARIAN_NUMBERS = {
    "egy": 1,
    "kettő": 2,
    "ketto": 2,
    "két": 2,
    "ket": 2,
    "három": 3,
    "harom": 3,
    "négy": 4,
    "negy": 4,
    "öt": 5,
    "ot": 5,
    "hat": 6,
}


def now_budapest() -> datetime:
    return datetime.now(ZoneInfo(get_settings().restaurant_timezone))


def create_initial_state(session_id: str) -> SessionState:
    now = now_budapest()
    state = SessionState(session_id=session_id, created_at=now, updated_at=now)
    state.missing_fields = compute_missing_fields(state)
    state.status = compute_status(state)
    state.last_assistant_message = "Üdvözlöm a Capri Pizzériában! Kérem, adja meg a telefonszámát."
    return state


def hydrate_state(payload: dict[str, Any]) -> SessionState:
    return SessionState.model_validate(payload)


def refresh_state(state: SessionState) -> SessionState:
    state.total_huf = sum(item.line_total_huf for item in state.cart)
    state.missing_fields = compute_missing_fields(state)
    state.status = compute_status(state)
    state.updated_at = now_budapest()
    return state


def compute_missing_fields(state: SessionState) -> list[str]:
    if state.status == "confirmed":
        return []

    missing: list[str] = []
    if not state.customer.phone:
        missing.append("phone")
    if not state.customer.profile_id and not state.customer.name:
        missing.append("customer_name_or_profile")
    if not state.fulfilment.type:
        missing.append("fulfilment_type")
    if state.fulfilment.type == "delivery" and not state.fulfilment.address_text:
        missing.append("delivery_address")
    if state.fulfilment.type == "pickup" and not state.fulfilment.pickup_time:
        missing.append("pickup_time")
    if not state.cart:
        missing.append("cart_items")
    if not state.payment_method:
        missing.append("payment_method")
    return missing


def compute_status(state: SessionState) -> str:
    if state.status == "confirmed":
        return "confirmed"
    if "phone" in state.missing_fields or "customer_name_or_profile" in state.missing_fields:
        return "awaiting_customer_identification"
    if "fulfilment_type" in state.missing_fields or "delivery_address" in state.missing_fields or "pickup_time" in state.missing_fields:
        return "awaiting_fulfilment_method"
    if "cart_items" in state.missing_fields:
        return "awaiting_items"
    if "payment_method" in state.missing_fields:
        return "awaiting_payment_method"
    return "awaiting_final_confirmation"


def normalize_fulfilment(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_text(value)
    if text in {"delivery", "hazhozszallitas", "kiszallitas"} or "hazhoz" in text or "kiszallit" in text:
        return "delivery"
    if text in {"pickup", "elvitel", "atvetel", "szemelyes atvetel"} or "atvetel" in text or "elvitel" in text:
        return "pickup"
    return None


def normalize_payment(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_text(value)
    if text in {"cash", "keszpenz", "kp"} or "keszpen" in text:
        return "cash"
    if text in {"card", "bankkartya", "kartya"} or "kartya" in text:
        return "card"
    return None


def normalize_size(value: str | None, item: MenuItem) -> str | None:
    if not item.sizes:
        return None
    if not value:
        return item.default_size
    text = normalize_text(value).replace(" ", "")
    for size in item.sizes:
        if text in {normalize_text(size.id).replace(" ", ""), normalize_text(size.label).replace(" ", "")}:
            return size.id
    if "45" in text:
        return "45cm"
    if "32" in text:
        return "32cm"
    return item.default_size


def item_unit_price(item: MenuItem, size: str | None) -> int:
    if item.sizes and size:
        matched = next((candidate for candidate in item.sizes if candidate.id == size), None)
        if matched:
            return matched.price_huf
    return item.base_price_huf


def is_restaurant_open() -> dict[str, Any]:
    menu = load_menu()
    current = now_budapest()
    day_key = current.strftime("%A").lower()
    interval = menu.restaurant.opening_hours.get(day_key)
    if not interval:
        return {"open": False, "reason": "No opening hours for today."}

    start_raw, end_raw = interval
    start_hour, start_minute = [int(part) for part in start_raw.split(":")]
    end_hour, end_minute = [int(part) for part in end_raw.split(":")]
    start = current.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end = current.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return {
        "open": start <= current <= end,
        "today": current.strftime("%A"),
        "current_time": current.strftime("%H:%M"),
        "hours": interval,
    }


def apply_llm_action(state: SessionState, action: LLMAction) -> tuple[SessionState, dict[str, Any]]:
    validation: dict[str, Any] = {
        "errors": [],
        "warnings": [],
        "rejected_cart_actions": [],
        "restaurant_opening": is_restaurant_open(),
    }
    applied_changes: list[str] = []

    if action.customer_updates.phone:
        phone = normalize_phone(action.customer_updates.phone)
        state.customer.phone = phone
        applied_changes.append("customer.phone")
        profile = find_customer_by_phone(phone)
        if profile:
            state.customer.profile_id = profile.id
            state.customer.name = profile.name
            state.customer.profile_found = True
            state.customer.profile_unresolved = False
            state.customer.addresses = profile.addresses
            applied_changes.append("customer.profile")
            if state.fulfilment.type == "delivery" and len(profile.addresses) == 1 and not state.fulfilment.address_text:
                address = profile.addresses[0]
                state.fulfilment.address_id = address.id
                state.fulfilment.address_text = address.full_address
                state.fulfilment.address_unverified = False
                applied_changes.append("fulfilment.saved_address")
        else:
            state.customer.profile_id = None
            state.customer.profile_found = False
            state.customer.profile_unresolved = True
            validation["warnings"].append("No mock customer profile found for phone number.")

    if action.customer_updates.name:
        state.customer.name = action.customer_updates.name.strip()
        applied_changes.append("customer.name")

    fulfilment_type = normalize_fulfilment(action.fulfilment_updates.type)
    if fulfilment_type:
        state.fulfilment.type = fulfilment_type  # type: ignore[assignment]
        applied_changes.append("fulfilment.type")
        if fulfilment_type == "delivery" and len(state.customer.addresses) == 1 and not state.fulfilment.address_text:
            address = state.customer.addresses[0]
            state.fulfilment.address_id = address.id
            state.fulfilment.address_text = address.full_address
            state.fulfilment.address_unverified = False
            applied_changes.append("fulfilment.saved_address")

    if action.fulfilment_updates.address_text:
        state.fulfilment.address_text = action.fulfilment_updates.address_text.strip()
        state.fulfilment.address_id = None
        state.fulfilment.address_unverified = True
        applied_changes.append("fulfilment.address_text")

    if action.fulfilment_updates.pickup_time:
        state.fulfilment.pickup_time = action.fulfilment_updates.pickup_time.strip()
        applied_changes.append("fulfilment.pickup_time")

    payment_method = normalize_payment(action.payment_method)
    if payment_method:
        state.payment_method = payment_method  # type: ignore[assignment]
        applied_changes.append("payment_method")

    for cart_action in action.cart_actions:
        if cart_action.operation != "add_item":
            validation["warnings"].append(f"Unsupported cart operation ignored: {cart_action.operation}")
            continue
        add_cart_item(state, cart_action, validation, applied_changes)

    state = refresh_state(state)
    assistant_message = build_assistant_message(state, action, validation, applied_changes)
    state.last_assistant_message = assistant_message
    state.updated_at = now_budapest()

    return state, {"validation": validation, "applied_changes": applied_changes, "assistant_message": assistant_message}


def local_action_for_message(user_text: str, state: SessionState) -> LLMAction | None:
    phone = extract_phone_only(user_text)
    if phone and "phone" in state.missing_fields:
        return LLMAction(
            reasoning_summary="Phone number extracted locally without LLM.",
            confidence=1.0,
            customer_updates={"phone": phone},
            suggested_assistant_response_hu=None,
        )

    fulfilment_type = normalize_fulfilment(user_text)
    if fulfilment_type and (
        "fulfilment_type" in state.missing_fields
        or "delivery_address" in state.missing_fields
        or "pickup_time" in state.missing_fields
    ):
        return LLMAction(
            reasoning_summary="Fulfilment method extracted locally without LLM.",
            confidence=1.0,
            fulfilment_updates={"type": fulfilment_type},
            suggested_assistant_response_hu=None,
        )

    payment_method = normalize_payment(user_text)
    if payment_method and "payment_method" in state.missing_fields:
        return LLMAction(
            reasoning_summary="Payment method extracted locally without LLM.",
            confidence=1.0,
            payment_method=payment_method,
            suggested_assistant_response_hu=None,
        )

    cart_action = extract_single_cart_action(user_text)
    if cart_action and ("cart_items" in state.missing_fields or state.status in {"awaiting_items", "awaiting_payment_method"}):
        return LLMAction(
            reasoning_summary="Single cart item extracted locally without LLM.",
            confidence=0.9,
            cart_actions=[cart_action],
            suggested_assistant_response_hu=None,
        )

    return None


def extract_phone_only(user_text: str) -> str | None:
    stripped = user_text.strip()
    digits = normalize_phone(stripped)
    if not digits or len(digits) < 8:
        return None

    leftover = re.sub(r"[\d\s+\-()/]", "", stripped)
    if leftover:
        return None
    return digits


def extract_single_cart_action(user_text: str) -> CartAction | None:
    normalized = normalize_text(user_text)
    candidates = [item for item in load_menu().items if menu_item_mentioned(item, normalized)]
    if len(candidates) != 1:
        return None

    item = candidates[0]
    return CartAction(
        operation="add_item",
        item_query=item.name_hu,
        menu_item_id=item.id,
        quantity=extract_quantity(normalized),
        size=extract_size_from_text(normalized),
        extra_toppings=extract_extra_toppings(item, normalized),
        removed_ingredients=extract_removed_ingredients(item, normalized),
        notes="",
    )


def menu_item_mentioned(item: MenuItem, normalized_text: str) -> bool:
    searchable = [item.name_hu, item.name_en, *item.aliases]
    return any(normalize_text(value) in normalized_text for value in searchable)


def extract_quantity(normalized_text: str) -> int:
    digit_match = re.search(r"\b([1-9]|1\d|20)\b", normalized_text)
    if digit_match:
        return int(digit_match.group(1))
    for word, number in HUNGARIAN_NUMBERS.items():
        if re.search(rf"\b{re.escape(normalize_text(word))}\b", normalized_text):
            return number
    return 1


def extract_size_from_text(normalized_text: str) -> str | None:
    if re.search(r"\b45\s*(cm|centis|centi|os)?\b", normalized_text):
        return "45cm"
    if re.search(r"\b32\s*(cm|centis|centi|es)?\b", normalized_text):
        return "32cm"
    return None


def extract_extra_toppings(item: MenuItem, normalized_text: str) -> list[str]:
    extras: list[str] = []
    for topping in item.allowed_extra_toppings:
        if normalize_text(topping) in normalized_text:
            extras.append(topping)
    return extras


def extract_removed_ingredients(item: MenuItem, normalized_text: str) -> list[str]:
    removed: list[str] = []
    removal_markers = ("nelkul", "ne legyen", "hagyd le", "haggyuk le")
    if not any(marker in normalized_text for marker in removal_markers):
        return removed
    for ingredient in item.ingredients:
        if normalize_text(ingredient) in normalized_text:
            removed.append(ingredient)
    return removed


def add_cart_item(
    state: SessionState,
    cart_action: CartAction,
    validation: dict[str, Any],
    applied_changes: list[str],
) -> None:
    item: MenuItem | None = None
    if cart_action.menu_item_id:
        item = get_menu_item(cart_action.menu_item_id)
        if not item:
            validation["rejected_cart_actions"].append(
                {"action": cart_action.model_dump(), "reason": "Unknown menu_item_id."}
            )
            return

    if not item:
        candidates = match_menu_candidates(cart_action.item_query)
        if len(candidates) == 1:
            item = candidates[0]
        elif len(candidates) > 1:
            validation["rejected_cart_actions"].append(
                {
                    "action": cart_action.model_dump(),
                    "reason": "Ambiguous item query.",
                    "candidates": [candidate.id for candidate in candidates],
                }
            )
            return
        else:
            validation["rejected_cart_actions"].append(
                {"action": cart_action.model_dump(), "reason": "Unknown menu item."}
            )
            return

    if not item.available:
        validation["rejected_cart_actions"].append(
            {"action": cart_action.model_dump(), "reason": "Menu item is unavailable.", "menu_item_id": item.id}
        )
        return

    extra_toppings = [topping.strip() for topping in cart_action.extra_toppings if topping.strip()]
    if len(extra_toppings) > 6:
        validation["rejected_cart_actions"].append(
            {"action": cart_action.model_dump(), "reason": "Maximum 6 extra toppings allowed per pizza."}
        )
        return

    allowed_lookup = {normalize_text(topping): topping for topping in item.allowed_extra_toppings}
    validated_extras: list[str] = []
    invalid_extras: list[str] = []
    for topping in extra_toppings:
        normalized = normalize_text(topping)
        if normalized in allowed_lookup:
            validated_extras.append(allowed_lookup[normalized])
        else:
            invalid_extras.append(topping)

    if invalid_extras:
        validation["rejected_cart_actions"].append(
            {
                "action": cart_action.model_dump(),
                "reason": "Unavailable or unknown extra topping.",
                "invalid_extra_toppings": invalid_extras,
                "allowed_extra_toppings": item.allowed_extra_toppings,
            }
        )
        return

    ingredient_lookup = {normalize_text(ingredient): ingredient for ingredient in item.ingredients}
    removed_ingredients: list[str] = []
    ignored_removed: list[str] = []
    for ingredient in cart_action.removed_ingredients:
        normalized = normalize_text(ingredient)
        if normalized in ingredient_lookup:
            removed_ingredients.append(ingredient_lookup[normalized])
        else:
            ignored_removed.append(ingredient)

    if ignored_removed:
        validation["warnings"].append(
            f"Some removed ingredients were not base ingredients for {item.name_hu}: {', '.join(ignored_removed)}"
        )

    size = normalize_size(cart_action.size, item)
    quantity = max(1, min(cart_action.quantity, 20))
    unit_price = item_unit_price(item, size)
    state.cart.append(
        CartItem(
            line_id=str(uuid4()),
            menu_item_id=item.id,
            display_name=item.name_hu,
            quantity=quantity,
            size=size,
            extra_toppings=validated_extras,
            removed_ingredients=removed_ingredients,
            notes=cart_action.notes.strip(),
            unit_price_huf=unit_price,
            line_total_huf=unit_price * quantity,
        )
    )
    applied_changes.append(f"cart.add:{item.id}")


def build_assistant_message(
    state: SessionState,
    action: LLMAction,
    validation: dict[str, Any],
    applied_changes: list[str],
) -> str:
    rejected = validation.get("rejected_cart_actions") or []
    if rejected:
        first = rejected[0]
        reason = first.get("reason", "Nem tudtam rögzíteni ezt a tételt.")
        if reason == "Unknown menu item.":
            return "Ezt az ételt nem találom az étlapon. Kérem, válasszon a megadott pizzák vagy italok közül."
        if reason == "Ambiguous item query.":
            return "Pontosítaná, melyik pizzára gondolt?"
        if reason == "Maximum 6 extra toppings allowed per pizza.":
            return "Egy pizzára legfeljebb 6 extra feltét kérhető. Kérem, adja meg újra a feltéteket."
        if reason == "Unavailable or unknown extra topping.":
            allowed = ", ".join(first.get("allowed_extra_toppings", []))
            return f"Ezt az extra feltétet nem tudjuk adni. Elérhető feltétek: {allowed}."
        return "Ezt a tételt nem tudtam rögzíteni. Kérem, pontosítsa a rendelést."

    if action.clarification.needed and action.clarification.question_hu:
        return action.clarification.question_hu

    if "phone" in state.missing_fields:
        return "Kérem, adja meg a telefonszámát a rendeléshez."
    if "customer_name_or_profile" in state.missing_fields:
        return "Nem találtam regisztrált profilt ehhez a számhoz. Kérem, adja meg a nevét."
    if "fulfilment_type" in state.missing_fields:
        return "Kiszállítással vagy személyes átvétellel kéri?"
    if "delivery_address" in state.missing_fields:
        return "Milyen címre kéri a kiszállítást?"
    if "pickup_time" in state.missing_fields:
        return "Mikorra kéri a személyes átvételt? Mondhatja azt is, hogy amint lehet."
    if "cart_items" in state.missing_fields:
        return "Mit készíthetünk?"
    if "payment_method" in state.missing_fields:
        return "Készpénzzel vagy bankkártyával szeretne fizetni?"

    return f"Rendben, összefoglalom: {order_summary_hu(state)}. Megerősíti a rendelést?"


def order_summary_hu(state: SessionState) -> str:
    item_parts = []
    for item in state.cart:
        size = f" {item.size}" if item.size else ""
        extras = f", extra: {', '.join(item.extra_toppings)}" if item.extra_toppings else ""
        removed = f", nélküle: {', '.join(item.removed_ingredients)}" if item.removed_ingredients else ""
        item_parts.append(f"{item.quantity} db{size} {item.display_name}{extras}{removed}")

    fulfilment = "kiszállítással" if state.fulfilment.type == "delivery" else "személyes átvételre"
    if state.fulfilment.type == "delivery" and state.fulfilment.address_text:
        fulfilment += f" ide: {state.fulfilment.address_text}"
    if state.fulfilment.type == "pickup" and state.fulfilment.pickup_time:
        fulfilment += f", időpont: {state.fulfilment.pickup_time}"

    payment = "készpénzes fizetéssel" if state.payment_method == "cash" else "bankkártyás fizetéssel"
    return f"{'; '.join(item_parts)}, {fulfilment}, {payment}. Végösszeg: {state.total_huf} Ft"
