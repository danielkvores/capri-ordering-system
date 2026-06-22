from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


OrderStatus = Literal[
    "active",
    "awaiting_customer_identification",
    "awaiting_fulfilment_method",
    "awaiting_items",
    "awaiting_clarification",
    "awaiting_payment_method",
    "awaiting_final_confirmation",
    "confirmed",
    "cancelled",
    "failed",
]

FulfilmentType = Literal["delivery", "pickup"]
PaymentMethod = Literal["cash", "card"]


class MenuSize(BaseModel):
    id: str
    label: str
    price_huf: int


class MenuItem(BaseModel):
    id: str
    name_hu: str
    name_en: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    base_price_huf: int
    available: bool = True
    sizes: list[MenuSize] = Field(default_factory=list)
    default_size: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    allowed_extra_toppings: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)


class RestaurantInfo(BaseModel):
    name: str
    timezone: str
    opening_hours: dict[str, list[str]]


class MenuPayload(BaseModel):
    restaurant: RestaurantInfo
    items: list[MenuItem]


class CustomerAddress(BaseModel):
    id: str
    label: str
    full_address: str


class CustomerProfile(BaseModel):
    id: str
    name: str
    phone: str
    addresses: list[CustomerAddress] = Field(default_factory=list)


class CustomerState(BaseModel):
    profile_id: str | None = None
    name: str | None = None
    phone: str | None = None
    profile_found: bool = False
    profile_unresolved: bool = False
    addresses: list[CustomerAddress] = Field(default_factory=list)


class FulfilmentState(BaseModel):
    type: FulfilmentType | None = None
    address_id: str | None = None
    address_text: str | None = None
    address_unverified: bool = False
    pickup_time: str | None = None


class CartItem(BaseModel):
    line_id: str
    menu_item_id: str
    display_name: str
    quantity: int
    size: str | None = None
    extra_toppings: list[str] = Field(default_factory=list)
    removed_ingredients: list[str] = Field(default_factory=list)
    notes: str = ""
    unit_price_huf: int
    line_total_huf: int


class SessionState(BaseModel):
    session_id: str
    status: OrderStatus = "active"
    language: Literal["hu"] = "hu"
    customer: CustomerState = Field(default_factory=CustomerState)
    fulfilment: FulfilmentState = Field(default_factory=FulfilmentState)
    payment_method: PaymentMethod | None = None
    cart: list[CartItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    total_huf: int = 0
    last_user_message: str | None = None
    last_assistant_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class CustomerUpdates(BaseModel):
    name: str | None = None
    phone: str | None = None


class FulfilmentUpdates(BaseModel):
    type: str | None = None
    address_text: str | None = None
    pickup_time: str | None = None


class CartAction(BaseModel):
    operation: str = "add_item"
    item_query: str | None = None
    menu_item_id: str | None = None
    quantity: int = Field(default=1, ge=1, le=20)
    size: str | None = None
    extra_toppings: list[str] = Field(default_factory=list)
    removed_ingredients: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("item_query", "menu_item_id", "size", "notes", mode="before")
    @classmethod
    def none_string_to_default(cls, value: Any, info: Any) -> Any:
        if value is None and info.field_name == "notes":
            return ""
        return value

    @field_validator("extra_toppings", "removed_ingredients", mode="before")
    @classmethod
    def none_list_to_default(cls, value: Any) -> Any:
        if value is None:
            return []
        return value


class Clarification(BaseModel):
    needed: bool = False
    question_hu: str | None = None
    reason: str | None = None


class LLMAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reasoning_summary: str | None = None
    language: str = "hu"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    customer_updates: CustomerUpdates = Field(default_factory=CustomerUpdates)
    fulfilment_updates: FulfilmentUpdates = Field(default_factory=FulfilmentUpdates)
    payment_method: str | None = None
    cart_actions: list[CartAction] = Field(default_factory=list)
    clarification: Clarification = Field(default_factory=Clarification)
    suggested_assistant_response_hu: str | None = None


class DebugPayload(BaseModel):
    llm_raw: str | None = None
    parsed_action: dict[str, Any] | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    applied_changes: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    errors: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session: SessionState
    messages: list[ChatMessage]


class MessageResponse(BaseModel):
    assistant_message: str
    session: SessionState
    messages: list[ChatMessage]
    debug: DebugPayload


class ConfirmResponse(BaseModel):
    assistant_message: str
    session: SessionState
    messages: list[ChatMessage]
    debug: DebugPayload
