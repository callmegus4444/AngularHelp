"""
session_store.py — In-memory session & conversation manager
============================================================
Stores per-session state so the frontend chatbox can maintain
multi-turn memory without any database.

Each session contains:
  conversation_history  — messages list for component_agent context
  last_component        — most recently generated ComponentData
  chat_log              — rendered chat panel entries (user + assistant)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatEntry:
    role: str           # "user" | "assistant"
    content: str        # raw text
    summary: str = ""   # short LLM-generated summary (assistant only)


@dataclass
class Session:
    session_id: str
    conversation_history: list[dict] = field(default_factory=list)
    last_component: Any = None          # ComponentData | None
    chat_log: list[ChatEntry] = field(default_factory=list)


# Single global store — keyed by session_id string
_STORE: dict[str, Session] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def create_session() -> str:
    """Create a new session, return its UUID string."""
    sid = str(uuid.uuid4())
    _STORE[sid] = Session(session_id=sid)
    return sid


def get_session(session_id: str) -> Session | None:
    return _STORE.get(session_id)


def get_or_create(session_id: str | None) -> Session:
    """Return existing session or create one if id is unknown/None."""
    if session_id and session_id in _STORE:
        return _STORE[session_id]
    sid = create_session()
    return _STORE[sid]


def reset_session(session_id: str) -> str:
    """Wipe a session and return a fresh session_id."""
    _STORE.pop(session_id, None)
    return create_session()


def append_user_turn(session: Session, prompt: str) -> None:
    session.conversation_history.append({"role": "user", "content": prompt})
    session.chat_log.append(ChatEntry(role="user", content=prompt))


def append_assistant_turn(session: Session, component_name: str, summary: str) -> None:
    msg = f"Generated component '{component_name}' successfully."
    session.conversation_history.append({"role": "assistant", "content": msg})
    session.chat_log.append(
        ChatEntry(role="assistant", content=msg, summary=summary)
    )


def build_agent_history(session: Session) -> list[dict]:
    """
    Return the conversation history slice to pass to component_agent,
    excluding the very last user turn (the agent receives that as user_prompt).
    """
    return session.conversation_history[:-1]
