# Restaurant Voice Ordering Prototype

Text-only Milestone 1 prototype for a Hungarian restaurant ordering assistant.

## What is included

- FastAPI backend
- React/Vite frontend
- SQLite persistence
- Mock Italian/pizza menu
- Mock customer profiles
- OpenRouter LLM provider abstraction
- Hungarian customer conversation
- English debug UI
- Backend-owned order state and validation
- Raw JSON debug panel

Audio, Whisper, TTS, Docker, deployment, and tests are intentionally not implemented yet.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.example .env
```

Edit `backend/.env`:

```env
DATABASE_URL=sqlite:///./restaurant_orders.db
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=your-openrouter-model-id
OPENROUTER_SITE_URL=http://localhost:5173
OPENROUTER_APP_NAME=Restaurant Ordering Prototype
```

Run the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

## Frontend setup

This project is Bun-first for frontend package management.

Install Bun if needed:

```bash
curl -fsSL https://bun.sh/install | bash
```

Restart your terminal after installation, then run:

```bash
cd frontend
bun install
bun run dev
```

Open `http://localhost:5173`.

## Optional local smoke test mode

For a limited no-network backend smoke test, set this in `backend/.env`:

```env
LLM_PROVIDER=mock
```

The mock provider only understands a narrow subset of Hungarian phrases and is not a replacement for OpenRouter.

## Known limitations

- The LLM extraction quality depends on the selected OpenRouter model.
- The mock provider is intentionally incomplete.
- No audio input, Whisper, TTS, Docker, production deployment, or tests yet.
- Menu matching is simple alias/query matching, not semantic search.
- New delivery addresses are stored as unverified text only.
- Opening-hours handling is advisory in Milestone 1 and does not block draft orders.
- Cart editing is basic; the strongest path is adding items and confirming once all required fields are present.
