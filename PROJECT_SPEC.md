
# PROJECT SPEC: Local Restaurant Voice Ordering Prototype

## 0. Project summary

Build a local-first prototype of a restaurant ordering assistant for an Italian/pizza restaurant.

The goal is not yet production deployment. The goal is to validate whether a simple voice/text ordering loop can reliably:

1. understand Hungarian customer order requests;
2. update a structured cart/order form;
3. ask clarification questions;
4. use a menu database rather than hallucinated menu knowledge;
5. save draft/confirmed orders;
6. expose enough debug information to inspect every step.

The first version should run locally on a MacBook Pro M4 with 32GB RAM.

The application should have a simple English-language web interface. The assistant/customer language should be Hungarian.

The initial version should be text-only. Later versions will add speech-to-text and then text-to-speech.

---

## 1. Hardware and environment

Target machine:

* MacBook Pro M4, 10-core CPU / 10-core GPU
* 32GB RAM
* macOS
* Local development with Codex app on Mac

The project may use Docker if useful, but Docker should not be required for the earliest working prototype unless it significantly simplifies setup.

The project should be designed so that model providers are swappable:

* Local Ollama models
* OpenRouter-hosted free/cheap models
* Later: DeepSeek/OpenAI/Gemini/etc.

---

## 2. Technology choices

### Backend

Use:

* Python
* FastAPI
* Pydantic
* SQLite
* SQLModel or SQLAlchemy, whichever is simpler and reliable
* Uvicorn for local development

### Frontend

Use:

* React
* Vite
* TypeScript preferred
* Basic styling is enough
* shadcn/ui or Base UI may be used if setup is straightforward, but do not overbuild the UI

The UI should be simple, functional, and developer/debugging-oriented.

### LLM layer

Use an abstract provider interface.

Initial supported providers:

1. OpenRouter provider
2. Optional Ollama provider

The app should read model/provider configuration from environment variables.

Example `.env` values:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
OLLAMA_MODEL=...
```

Do not hard-code a specific model. The user may test free OpenRouter models such as DeepSeek, Nemotron, Gemma, Qwen, or others.

### Speech-to-text

Not required in Milestone 1.

For later milestones:

* local Whisper/faster-whisper
* browser microphone recording
* backend transcription endpoint

### Text-to-speech

Not required in Milestone 1.

For later milestones:

* browser speech synthesis first
* Piper/local TTS later
* Hungarian TTS support eventually required

---

## 3. Core principle

The LLM must not be the source of truth.

The backend owns the order state.

The LLM’s job is to convert the latest user message into structured proposed actions. The backend validates those actions against the menu, customer profile, business rules, and current session state.

Bad design:

```text
User message → LLM remembers everything → LLM gives final order
```

Good design:

```text
User message
→ LLM proposes JSON actions
→ backend validates
→ backend updates order state
→ backend computes missing fields
→ backend sends validated state back to LLM/response generator
→ assistant asks next question or confirms progress
```

The model should never directly mutate the database.

---

## 4. Product scope

### In scope for v0.1

* Local web UI
* Text input
* Hungarian ordering conversation
* Italian/pizza restaurant mock menu
* Order state/cart display
* Basic customer profile lookup from mock database
* Pickup or delivery selection
* Cash or card payment selection
* Opening-hours awareness
* Item availability awareness
* Raw debug JSON display
* Session reset
* Draft order saving
* Confirmed order saving
* Logs of messages, LLM outputs, validation results, and latency

### Out of scope for v0.1

* Real phone calls
* Continuous voice call
* Streaming audio
* Production telephony
* Real POS integration
* Real payment processing
* User authentication
* Human fallback
* Production deployment
* Complex menu ingestion from PDF
* Full bilingual UI

---

## 5. Interface language and assistant language

The web interface should be in English.

Examples:

* “Start New Session”
* “Send Text”
* “Current Order”
* “Debug JSON”
* “Conversation”
* “Customer Profile”
* “Confirm Order”

The assistant should speak/write Hungarian to the customer.

The system should assume Hungarian user input. English input is not required.

---

## 6. First restaurant domain

Use a mock Italian/pizza restaurant.

Start with pizzas only, because pizzas are complex enough for concept validation due to:

* sizes
* toppings
* removed ingredients
* extra ingredients
* quantity changes
* modifiers
* allergens
* availability

A small menu is enough.

Example menu items:

* Margherita pizza
* Pepperoni pizza
* Prosciutto pizza
* Quattro Formaggi pizza
* Vegetarian pizza
* Coca-Cola
* Mineral water

Each pizza should support:

* size: 32cm / 45cm
* optional extra toppings
* removed toppings
* notes

The mock menu should be hand-written JSON.

Do not implement PDF/menu extraction in v0.1.

---

## 7. Customer profile concept

In production, only registered users would use this service. The database would contain:

* name
* phone number
* saved delivery addresses
* possibly previous orders

For v0.1, implement a mock customer profile database.

Example:

```json
[
  {
    "id": "cust_001",
    "name": "Kovács Dániel",
    "phone": "36701234567",
    "addresses": [
      {
        "id": "addr_001",
        "label": "Home",
        "full_address": "1053 Budapest, Kossuth Lajos utca 10."
      }
    ]
  }
]
```

The assistant should be able to ask for or detect a phone number, look up the profile, and use saved name/address data.

However, v0.1 should also support manual test sessions where no phone lookup is done yet.

---

## 8. Order flow

The assistant should follow this broad flow, but should not be rigid if the customer provides information out of order.

### Step 1: Identify customer

Ask for phone number if missing.

Rules:

* Hungarian phone numbers should be normalised to digits only.
* Remove spaces, hyphens, parentheses.
* If a profile is found, use the saved name and address.
* If no profile is found, ask once more for the number.
* If still not found, explain that the number is not registered in the mock system.

For prototype purposes, the system may still allow an unregistered draft order, but it should mark the profile as unresolved.

### Step 2: Fulfilment method

Ask whether the order is for:

* delivery
* pickup

Hungarian terms:

* “házhozszállítás”
* “kiszállítás”
* “személyes átvétel”
* “elvitel”
* “éttermi átvétel”

If delivery:

* use saved address if available;
* if multiple addresses exist, ask which one;
* if a new address is given, record it but mark it as “new/unverified” in v0.1.

Production rule note: later, new addresses may not be allowed unless added through account registration.

If pickup:

* ask for pickup time if missing.

### Step 3: Add items

The assistant should ask:

```hu
Mit készíthetünk?
```

The user may add multiple items in one message.

The backend should validate every item against the menu.

If the item is ambiguous, ask a clarification.

If the item is unavailable, say so and offer alternatives.

For pizzas, handle:

* quantity
* size
* extra toppings
* removed toppings
* notes
* allergies if mentioned

The system should enforce:

* maximum 6 extra toppings per pizza
* unavailable toppings cannot be added
* unknown menu items cannot be added without clarification

### Step 4: Payment method

Supported payment methods:

* cash
* card

Hungarian:

* “készpénz”
* “bankkártya”
* “kártya”

### Step 5: Confirmation

Before confirming the order, required fields should be complete.

Required fields:

* customer name or profile
* phone number
* fulfilment type
* if delivery: address
* if pickup: pickup time or “as soon as possible”
* at least one cart item
* payment method

The assistant should provide a concise final summary in Hungarian and ask for confirmation.

Example:

```hu
Rendben, összefoglalom: két 32 cm-es Margherita pizza extra sajttal, személyes átvételre, bankkártyás fizetéssel. Megerősíted a rendelést?
```

Only after explicit confirmation should the order status become `confirmed`.

---

## 9. State machine

Use explicit statuses.

Suggested session/order statuses:

```text
active
awaiting_customer_identification
awaiting_fulfilment_method
awaiting_items
awaiting_clarification
awaiting_payment_method
awaiting_final_confirmation
confirmed
cancelled
failed
```

The backend may compute the status after every turn based on missing fields.

The model can suggest a status, but the backend decides the true status.

---

## 10. Data models

### Menu item

```json
{
  "id": "pizza_margherita",
  "name_hu": "Margherita pizza",
  "name_en": "Margherita pizza",
  "aliases": ["margherita", "margaréta", "sajtos pizza", "paradicsomos sajtos pizza"],
  "category": "pizza",
  "base_price_huf": 2490,
  "available": true,
  "sizes": [
    {
      "id": "32cm",
      "label": "32 cm",
      "price_huf": 2490
    },
    {
      "id": "45cm",
      "label": "45 cm",
      "price_huf": 4490
    }
  ],
  "default_size": "32cm",
  "ingredients": ["paradicsomszósz", "mozzarella", "bazsalikom"],
  "allowed_extra_toppings": ["extra sajt", "sonka", "kukorica", "gomba", "olívabogyó", "jalapeno"],
  "allergens": ["glutén", "tej"]
}
```

### Customer profile

```json
{
  "id": "cust_001",
  "name": "Kovács Dániel",
  "phone": "36701234567",
  "addresses": [
    {
      "id": "addr_001",
      "label": "Otthon",
      "full_address": "1053 Budapest, Kossuth Lajos utca 10."
    }
  ]
}
```

### Session/order state

```json
{
  "session_id": "uuid",
  "status": "active",
  "language": "hu",
  "customer": {
    "profile_id": null,
    "name": null,
    "phone": null,
    "profile_found": false
  },
  "fulfilment": {
    "type": null,
    "address_id": null,
    "address_text": null,
    "pickup_time": null
  },
  "payment_method": null,
  "cart": [],
  "missing_fields": [],
  "last_user_message": null,
  "last_assistant_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### Cart item

```json
{
  "line_id": "uuid",
  "menu_item_id": "pizza_margherita",
  "display_name": "Margherita pizza",
  "quantity": 2,
  "size": "32cm",
  "extra_toppings": ["extra sajt"],
  "removed_ingredients": [],
  "notes": "",
  "unit_price_huf": 2490,
  "line_total_huf": 4980
}
```

---

## 11. LLM action schema

For v0.1, use one large structured JSON output from the model.

The model should return one object with:

```json
{
  "reasoning_summary": "short non-sensitive summary of what was understood",
  "language": "hu",
  "confidence": 0.0,
  "customer_updates": {
    "name": null,
    "phone": null
  },
  "fulfilment_updates": {
    "type": null,
    "address_text": null,
    "pickup_time": null
  },
  "payment_method": null,
  "cart_actions": [
    {
      "operation": "add_item",
      "item_query": "margherita pizza",
      "menu_item_id": null,
      "quantity": 1,
      "size": null,
      "extra_toppings": [],
      "removed_ingredients": [],
      "notes": ""
    }
  ],
  "clarification": {
    "needed": false,
    "question_hu": null,
    "reason": null
  },
  "suggested_assistant_response_hu": "..."
}
```

Important:

* The backend validates this object with Pydantic.
* The backend rejects invalid menu item IDs.
* The backend may search menu candidates before/after LLM output.
* The backend decides the final assistant message.
* If JSON parsing fails, retry once with a JSON repair prompt.
* If still invalid, ask the user to repeat/clarify.

---

## 12. Prompting rules for the restaurant assistant

The assistant role is based on the previous Hungarian dispatcher prompt, adapted for the local prototype.

### Role

You are a Hungarian-speaking restaurant dispatcher for an Italian/pizza restaurant. You take online/phone-style food orders for delivery or pickup. Your goal is to handle the conversation quickly, politely, and accurately.

### Communication rules

* Use Hungarian with the customer.
* Be brief and natural.
* Wait for the customer’s information.
* If you do not understand, ask for clarification.
* Do not thank the user after every item.
* Do not repeat unnecessarily.
* Do not discuss the technical system.
* Ask one clarification question at a time where possible.
* Do not invent menu items, prices, addresses, opening hours, or profile information.
* Do not say the order is confirmed until required fields are complete and the user explicitly confirms.

### Operational rules

* Use backend/menu data as the source of truth.
* If a menu item is missing or ambiguous, ask a clarification.
* If a topping is not available, say so.
* If more than 6 extra toppings are requested on one pizza, explain the limit.
* Prices should come from the menu database only.
* Item-level prices should only be read out if the user asks.
* The final total can be mentioned at payment/confirmation stage.
* For payment, ask whether the customer wants to pay by cash or card.
* For delivery, collect or select an address.
* For pickup, collect pickup time.
* At closing, say something like: “Köszönöm szépen a rendelést, további szép napot kívánok!”

---

## 13. Website UI requirements

The frontend should contain these panels.

### 1. Header

Show app name:

```text
Restaurant Voice Ordering Prototype
```

Show current session status.

Buttons:

* Start New Session
* Reset Session

### 2. Input panel

For Milestone 1:

* Textbox for Hungarian customer input
* Send button

Later:

* Start recording button
* Stop recording button
* Transcript preview

### 3. Conversation panel

Show message history:

* User messages
* Assistant messages

### 4. Current order panel

Show:

* customer name
* phone
* profile found/not found
* fulfilment type
* address
* pickup time
* payment method
* cart items
* total price
* missing fields
* status

### 5. Debug panel

Show raw JSON:

* last user input
* LLM raw response
* parsed action JSON
* validation result
* backend-applied changes
* latency timings
* errors

It is acceptable to show raw JSON directly in v0.1.

### 6. Menu panel

Show current mock menu.

At minimum:

* item name
* price
* availability
* possible toppings/modifiers

---

## 14. Backend endpoints

Suggested API endpoints:

```text
POST /api/sessions
GET  /api/sessions/{session_id}
POST /api/sessions/{session_id}/message
POST /api/sessions/{session_id}/reset
POST /api/sessions/{session_id}/confirm
GET  /api/menu
GET  /api/logs/{session_id}
```

Later:

```text
POST /api/sessions/{session_id}/audio
POST /api/sessions/{session_id}/tts
```

### POST /api/sessions/{session_id}/message

Request:

```json
{
  "text": "Szia, kérek két Margherita pizzát elvitelre."
}
```

Response:

```json
{
  "assistant_message": "Rendben, két Margherita pizzát rögzítettem. Mikorra kéred az átvételt?",
  "session": { "...": "updated session state" },
  "debug": {
    "llm_raw": "...",
    "parsed_action": {},
    "validation": {},
    "latency_ms": 1234
  }
}
```

---

## 15. Project structure

Use this structure unless Codex has a strong reason to simplify.

```text
restaurant-voice-prototype/
  README.md
  PROJECT_SPEC.md
  ARCHITECTURE.md
  TASKS.md
  .env.example
  .gitignore
  docker-compose.yml              # optional, may be added later
  backend/
    pyproject.toml
    app/
      main.py
      config.py
      db.py
      models.py
      schemas.py
      menu.py
      customers.py
      order_engine.py
      llm/
        base.py
        openrouter_provider.py
        ollama_provider.py
        prompts.py
      services/
        logging_service.py
        validation_service.py
      data/
        menu.json
        customers.json
    scripts/
      seed_db.py
  frontend/
    package.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      api.ts
      components/
        InputPanel.tsx
        ConversationPanel.tsx
        OrderPanel.tsx
        DebugPanel.tsx
        MenuPanel.tsx
      styles.css
```

---

## 16. Milestones

### Milestone 1: Text-only local web app

Build:

* FastAPI backend
* React/Vite frontend
* SQLite database
* mock menu
* mock customer profiles
* text input
* LLM provider abstraction
* OpenRouter provider
* session state
* order/cart update logic
* visible order panel
* debug panel
* draft/confirmed order status

Definition of done:

* App starts locally.
* User can start a session.
* User can type a Hungarian order.
* Backend calls configured LLM.
* LLM returns structured JSON.
* Backend validates and applies updates.
* UI shows conversation, order state, debug JSON.
* User can confirm order when required fields are complete.
* Order is saved locally.

### Milestone 2: Speech-to-text input

Add:

* browser audio recording
* audio upload endpoint
* faster-whisper/local Whisper transcription
* transcript display
* transcript passed into same message pipeline

Definition of done:

* User can record a short utterance.
* System transcribes Hungarian speech.
* Transcript appears in UI.
* Transcript updates the order like typed text.

### Milestone 3: Text-to-speech output

Add:

* TTS toggle
* browser speech synthesis first
* Hungarian voice if available
* assistant response spoken aloud

Definition of done:

* Assistant response is shown as text.
* Assistant response can be spoken aloud.
* TTS can be enabled/disabled.

### Milestone 4: Evaluation harness

Add:

* sample Hungarian order test cases
* script to run cases through the ordering pipeline
* metrics for JSON validity, item accuracy, quantity accuracy, missing-field logic, and confirmation correctness

Definition of done:

* `python scripts/evaluate.py` runs test cases.
* Results are printed in a readable table.
* Failures show expected vs actual.

### Milestone 5: Provider swapping and robustness

Add:

* Ollama provider if not already present
* retry logic for malformed JSON
* model/provider selection from UI or env
* better error states
* saved logs

---

## 17. Testing approach

Do not write full test coverage before the basic demo exists.

However, design the code so that tests can be added cleanly.

After Milestone 1 works, add tests for:

* menu matching
* cart updates
* required-field computation
* phone normalisation
* JSON parsing/validation
* confirmation rules

---

## 18. Important implementation notes

1. Keep the LLM provider abstract.
2. Keep menu data structured.
3. Do not let the LLM invent menu items.
4. Use Pydantic schemas aggressively.
5. Store all important state in SQLite, not only frontend memory.
6. Show debug information openly in v0.1.
7. Prefer simple working code over clever abstractions.
8. Do not implement streaming voice until text mode and push-to-talk mode are working.
9. Use environment variables for secrets.
10. Do not commit API keys.

---

## 19. First implementation task for Codex

Implement Milestone 1 only.

Build the text-only local web app according to this spec.

Prioritise:

1. working FastAPI backend;
2. working React/Vite frontend;
3. OpenRouter LLM provider abstraction;
4. mock menu and customer data;
5. typed Hungarian order input;
6. structured JSON extraction;
7. backend validation;
8. visible current order state;
9. debug panel.

Do not implement Whisper, microphone recording, TTS, Docker, evaluation scripts, or production deployment yet.

After implementing, provide:

* setup instructions;
* commands to run backend and frontend;
* explanation of `.env` values;
* known limitations;
* next recommended milestone.
