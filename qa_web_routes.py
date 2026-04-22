import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from uuapi_client import UUAPIError, normalize_model, send_chat


router = APIRouter(prefix="/api/web-chat", tags=["web-chat"])
STORE_DIR = Path(__file__).resolve().parent / "data"
STORE_PATH = STORE_DIR / "web_chat_sessions.json"
STORE_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_store() -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text("{}", encoding="utf-8")


def load_sessions() -> dict:
    ensure_store()
    with STORE_LOCK:
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


def save_sessions(data: dict) -> None:
    ensure_store()
    with STORE_LOCK:
        STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_title(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    return cleaned[:28] or "新对话"


def build_session(session_id: str, model: str) -> dict:
    timestamp = now_iso()
    return {
        "session_id": session_id,
        "title": "新对话",
        "model": normalize_model(model),
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }


class CreateSessionRequest(BaseModel):
    model: Literal["claude-opus-4-6", "claude-sonnet-4-6"] = "claude-sonnet-4-6"


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=20000)
    model: Literal["claude-opus-4-6", "claude-sonnet-4-6"] = "claude-sonnet-4-6"


@router.get("/sessions")
def list_sessions():
    sessions = load_sessions()
    items = sorted(sessions.values(), key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"sessions": items}


@router.post("/sessions")
def create_session(payload: CreateSessionRequest):
    sessions = load_sessions()
    session_id = str(uuid.uuid4())
    session = build_session(session_id, payload.model)
    sessions[session_id] = session
    save_sessions(sessions)
    return session


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    sessions = load_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    sessions = load_sessions()
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions.pop(session_id)
    save_sessions(sessions)
    return {"deleted": True, "session_id": session_id}


@router.post("/chat")
def chat(payload: ChatRequest):
    sessions = load_sessions()
    session_id = payload.session_id or str(uuid.uuid4())
    session = sessions.get(session_id) or build_session(session_id, payload.model)
    session["model"] = normalize_model(payload.model)

    user_message = {
        "role": "user",
        "content": payload.message.strip(),
        "created_at": now_iso(),
    }
    session["messages"].append(user_message)
    if session["title"] == "新对话":
        session["title"] = summarize_title(payload.message)

    try:
        result = send_chat(
            messages=[{"role": item["role"], "content": item["content"]} for item in session["messages"]],
            model=session["model"],
            session_id=session_id,
        )
    except UUAPIError as exc:
        logger.warning(
            "web-chat upstream error: session_id=%s status=%s code=%s content_type=%s preview=%s",
            session_id,
            exc.status_code,
            exc.error_code,
            exc.content_type,
            exc.response_preview,
        )
        return JSONResponse(
            status_code=502,
            content={
                "detail": exc.message,
                "error_code": exc.error_code,
                "upstream_status": exc.status_code,
            },
        )
    except Exception as exc:
        logger.exception("web-chat unexpected error: session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="聊天服务内部异常，请稍后重试。") from exc

    assistant_message = {
        "role": "assistant",
        "content": result["text"] or "模型返回了空内容。",
        "created_at": now_iso(),
    }
    session["messages"].append(assistant_message)
    session["updated_at"] = now_iso()
    sessions[session_id] = session
    save_sessions(sessions)
    return session
