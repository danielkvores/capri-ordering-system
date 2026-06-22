import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas import MenuItem, MenuPayload

DATA_PATH = Path(__file__).parent / "data" / "menu.json"


def normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    without_accents = "".join(
        char for char in unicodedata.normalize("NFD", lowered) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


@lru_cache
def load_menu() -> MenuPayload:
    return MenuPayload.model_validate(json.loads(DATA_PATH.read_text(encoding="utf-8")))


def get_menu_item(item_id: str) -> MenuItem | None:
    return next((item for item in load_menu().items if item.id == item_id), None)


def menu_for_prompt() -> list[dict]:
    result = []
    for item in load_menu().items:
        result.append(
            {
                "id": item.id,
                "name_hu": item.name_hu,
                "aliases": item.aliases,
                "category": item.category,
                "available": item.available,
                "sizes": [size.model_dump() for size in item.sizes],
                "default_size": item.default_size,
                "ingredients": item.ingredients,
                "allowed_extra_toppings": item.allowed_extra_toppings,
                "allergens": item.allergens,
            }
        )
    return result


def match_menu_candidates(query: str | None) -> list[MenuItem]:
    if not query:
        return []

    normalized_query = normalize_text(query)
    if not normalized_query:
        return []

    exact_matches: list[MenuItem] = []
    contains_matches: list[MenuItem] = []

    for item in load_menu().items:
        searchable = [item.id, item.name_hu, item.name_en, *item.aliases]
        normalized_values = [normalize_text(value) for value in searchable]
        if normalized_query in normalized_values:
            exact_matches.append(item)
        elif any(normalized_query in value or value in normalized_query for value in normalized_values):
            contains_matches.append(item)

    return exact_matches or contains_matches
