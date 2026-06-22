const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type OrderStatus =
  | "active"
  | "awaiting_customer_identification"
  | "awaiting_fulfilment_method"
  | "awaiting_items"
  | "awaiting_clarification"
  | "awaiting_payment_method"
  | "awaiting_final_confirmation"
  | "confirmed"
  | "cancelled"
  | "failed";

export type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  created_at: string;
};

export type CartItem = {
  line_id: string;
  menu_item_id: string;
  display_name: string;
  quantity: number;
  size: string | null;
  extra_toppings: string[];
  removed_ingredients: string[];
  notes: string;
  unit_price_huf: number;
  line_total_huf: number;
};

export type SessionState = {
  session_id: string;
  status: OrderStatus;
  language: "hu";
  customer: {
    profile_id: string | null;
    name: string | null;
    phone: string | null;
    profile_found: boolean;
    profile_unresolved: boolean;
    addresses: { id: string; label: string; full_address: string }[];
  };
  fulfilment: {
    type: "delivery" | "pickup" | null;
    address_id: string | null;
    address_text: string | null;
    address_unverified: boolean;
    pickup_time: string | null;
  };
  payment_method: "cash" | "card" | null;
  cart: CartItem[];
  missing_fields: string[];
  total_huf: number;
  last_user_message: string | null;
  last_assistant_message: string | null;
  created_at: string;
  updated_at: string;
};

export type MenuPayload = {
  restaurant: {
    name: string;
    timezone: string;
    opening_hours: Record<string, string[]>;
  };
  items: {
    id: string;
    name_hu: string;
    name_en: string;
    aliases: string[];
    category: string;
    base_price_huf: number;
    available: boolean;
    sizes: { id: string; label: string; price_huf: number }[];
    default_size: string | null;
    ingredients: string[];
    allowed_extra_toppings: string[];
    allergens: string[];
  }[];
};

export type DebugPayload = {
  llm_raw: string | null;
  parsed_action: unknown;
  validation: unknown;
  applied_changes: string[];
  latency_ms: number | null;
  errors: string[];
};

export type SessionResponse = {
  session: SessionState;
  messages: ChatMessage[];
};

export type MessageResponse = SessionResponse & {
  assistant_message: string;
  debug: DebugPayload;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createSession() {
  return request<SessionResponse>("/api/sessions", { method: "POST" });
}

export function getMenu() {
  return request<MenuPayload>("/api/menu");
}

export function sendMessage(sessionId: string, text: string) {
  return request<MessageResponse>(`/api/sessions/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function resetSession(sessionId: string) {
  return request<SessionResponse>(`/api/sessions/${sessionId}/reset`, { method: "POST" });
}

export function confirmOrder(sessionId: string) {
  return request<MessageResponse>(`/api/sessions/${sessionId}/confirm`, { method: "POST" });
}
