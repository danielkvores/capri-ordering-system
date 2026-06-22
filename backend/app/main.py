import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, init_db
from app.llm import build_provider
from app.menu import load_menu
from app.models import OrderLog, SessionRecord
from app.order_engine import (
    apply_llm_action,
    create_initial_state,
    hydrate_state,
    local_action_for_message,
    now_budapest,
    refresh_state,
)
from app.schemas import (
    ChatMessage,
    ConfirmResponse,
    DebugPayload,
    MessageRequest,
    MessageResponse,
    SessionResponse,
    SessionState,
)
from app.services.logging_service import add_log

settings = get_settings()

app = FastAPI(title="Restaurant Ordering Prototype API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionResponse)
def create_session(db: Session = Depends(get_db)) -> SessionResponse:
    session_id = str(uuid4())
    state = create_initial_state(session_id)
    messages = [ChatMessage(role="assistant", text=state.last_assistant_message or "", created_at=now_budapest())]
    record = SessionRecord(
        id=session_id,
        status=state.status,
        state_json=dump_json(state.model_dump(mode="json")),
        messages_json=dump_json([message.model_dump(mode="json") for message in messages]),
    )
    db.add(record)
    db.commit()
    add_log(db, session_id, "session_created", {"state": state.model_dump(mode="json")})
    return SessionResponse(session=state, messages=messages)


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionResponse:
    record = get_record_or_404(db, session_id)
    return response_from_record(record)


@app.post("/api/sessions/{session_id}/message", response_model=MessageResponse)
async def post_message(session_id: str, request: MessageRequest, db: Session = Depends(get_db)) -> MessageResponse:
    record = get_record_or_404(db, session_id)
    state = state_from_record(record)
    messages = messages_from_record(record)
    state.last_user_message = request.text

    local_action = local_action_for_message(request.text, state)
    if local_action:
        llm_result = None
        debug = DebugPayload(
            llm_raw=None,
            parsed_action=local_action.model_dump(mode="json"),
            latency_ms=0,
            errors=[],
        )
        state, result = apply_llm_action(state, local_action)
        assistant_message = result["assistant_message"]
        debug.validation = result["validation"]
        debug.applied_changes = ["local.phone_extract", *result["applied_changes"]]
    else:
        try:
            provider = build_provider(settings)
            llm_result = await provider.extract_actions(request.text, state)
            debug = DebugPayload(
                llm_raw=llm_result.raw,
                parsed_action=llm_result.action.model_dump(mode="json") if llm_result.action else None,
                latency_ms=llm_result.latency_ms,
                errors=llm_result.errors,
            )
        except Exception as exc:
            llm_result = None
            debug = DebugPayload(errors=[f"{type(exc).__name__}: {exc}"])

        if llm_result is None or llm_result.action is None:
            assistant_message = assistant_message_for_llm_error(debug.errors)
            state.last_assistant_message = assistant_message
            state = refresh_state(state)
        else:
            state, result = apply_llm_action(state, llm_result.action)
            assistant_message = result["assistant_message"]
            debug.validation = result["validation"]
            debug.applied_changes = result["applied_changes"]

    messages.append(ChatMessage(role="user", text=request.text, created_at=now_budapest()))
    messages.append(ChatMessage(role="assistant", text=assistant_message, created_at=now_budapest()))

    save_record(db, record, state, messages)
    add_log(
        db,
        session_id,
        "message_processed",
        {
            "user_text": request.text,
            "assistant_message": assistant_message,
            "debug": debug.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
        },
    )
    return MessageResponse(assistant_message=assistant_message, session=state, messages=messages, debug=debug)


@app.post("/api/sessions/{session_id}/reset", response_model=SessionResponse)
def reset_session(session_id: str, db: Session = Depends(get_db)) -> SessionResponse:
    record = get_record_or_404(db, session_id)
    state = create_initial_state(session_id)
    messages = [ChatMessage(role="assistant", text=state.last_assistant_message or "", created_at=now_budapest())]
    save_record(db, record, state, messages)
    add_log(db, session_id, "session_reset", {"state": state.model_dump(mode="json")})
    return SessionResponse(session=state, messages=messages)


@app.post("/api/sessions/{session_id}/confirm", response_model=ConfirmResponse)
def confirm_session(session_id: str, db: Session = Depends(get_db)) -> ConfirmResponse:
    record = get_record_or_404(db, session_id)
    state = refresh_state(state_from_record(record))
    messages = messages_from_record(record)
    debug = DebugPayload(validation={"missing_fields": state.missing_fields})

    if state.status == "confirmed":
        assistant_message = "A rendelés már meg van erősítve."
    elif state.missing_fields:
        assistant_message = "Még nem tudom lezárni a rendelést. Hiányzó adatok: " + ", ".join(state.missing_fields) + "."
    else:
        state.status = "confirmed"
        state.missing_fields = []
        state.updated_at = now_budapest()
        assistant_message = "Köszönöm szépen a rendelést, rögzítettem. További szép napot kívánok!"
        debug.applied_changes = ["status.confirmed"]

    state.last_assistant_message = assistant_message
    messages.append(ChatMessage(role="assistant", text=assistant_message, created_at=now_budapest()))
    save_record(db, record, state, messages)
    add_log(
        db,
        session_id,
        "order_confirm_attempt",
        {"assistant_message": assistant_message, "debug": debug.model_dump(mode="json"), "state": state.model_dump(mode="json")},
    )
    return ConfirmResponse(assistant_message=assistant_message, session=state, messages=messages, debug=debug)


@app.get("/api/menu")
def get_menu() -> dict[str, Any]:
    return load_menu().model_dump(mode="json")


@app.get("/api/logs/{session_id}")
def get_logs(session_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    logs = (
        db.query(OrderLog)
        .filter(OrderLog.session_id == session_id)
        .order_by(OrderLog.created_at.asc(), OrderLog.id.asc())
        .all()
    )
    return [
        {
            "id": log.id,
            "session_id": log.session_id,
            "event_type": log.event_type,
            "payload": json.loads(log.payload_json),
            "created_at": log.created_at,
        }
        for log in logs
    ]


def get_record_or_404(db: Session, session_id: str) -> SessionRecord:
    record = db.get(SessionRecord, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


def response_from_record(record: SessionRecord) -> SessionResponse:
    return SessionResponse(session=state_from_record(record), messages=messages_from_record(record))


def state_from_record(record: SessionRecord) -> SessionState:
    return hydrate_state(json.loads(record.state_json))


def messages_from_record(record: SessionRecord) -> list[ChatMessage]:
    return [ChatMessage.model_validate(message) for message in json.loads(record.messages_json)]


def save_record(db: Session, record: SessionRecord, state: SessionState, messages: list[ChatMessage]) -> None:
    record.status = state.status
    record.state_json = dump_json(state.model_dump(mode="json"))
    record.messages_json = dump_json([message.model_dump(mode="json") for message in messages])
    record.updated_at = datetime.utcnow()
    db.add(record)
    db.commit()
    db.refresh(record)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def assistant_message_for_llm_error(errors: list[str]) -> str:
    joined = " ".join(errors).lower()
    if "429" in joined or "too many requests" in joined:
        return "A modell szolgáltató most túl sok kérést jelez. A telefonszámot helyben tudom kezelni, de a rendelési szöveget próbálja meg kicsit később."
    return "Elnézést, nem tudtam biztonságosan feldolgozni az üzenetet. Kérem, ismételje meg rövidebben."
