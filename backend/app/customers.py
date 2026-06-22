import json
import re
from functools import lru_cache
from pathlib import Path

from app.schemas import CustomerProfile

DATA_PATH = Path(__file__).parent / "data" / "customers.json"


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits or None


@lru_cache
def load_customers() -> list[CustomerProfile]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [CustomerProfile.model_validate(profile) for profile in raw]


def find_customer_by_phone(phone: str | None) -> CustomerProfile | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    return next((profile for profile in load_customers() if normalize_phone(profile.phone) == normalized), None)
