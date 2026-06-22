import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import OrderLog


def add_log(db: Session, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
    db.add(
        OrderLog(
            session_id=session_id,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
    )
    db.commit()
