# Architecture

Milestone 1 uses a local browser UI, a FastAPI backend, and SQLite.

## Request flow

1. The customer enters Hungarian text in the React UI.
2. The frontend sends the text to `POST /api/sessions/{session_id}/message`.
3. The backend sends current state, menu data, and the latest text to the configured LLM provider.
4. The LLM returns structured JSON proposed actions.
5. The backend validates the proposal against the menu, mock profiles, and order rules.
6. The backend updates the SQLite-backed session state.
7. The backend recomputes missing fields, status, totals, and the assistant response.
8. The frontend renders the conversation, current order, menu, and debug JSON.

The LLM never directly owns or persists the cart/order state.

## Persistence

SQLite stores:

- session state JSON
- conversation messages JSON
- order/debug logs

The mock menu and customer profiles are hand-written JSON files under `backend/app/data`.
