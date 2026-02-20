"""
server.py — AngularHelp FastAPI Bridge
======================================
Wraps the existing LangGraph component_agent and preview.py utilities
behind a REST API, and serves the frontend static files.

Start with:
    uv run uvicorn frontend.api.server:app --reload --port 8000
"""

from __future__ import annotations

import sys
import pathlib

# ── Make project root importable so `agent.*` can be found ──
_ROOT = pathlib.Path(__file__).resolve().parents[2]   # d:\coder-buddy-main
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Lazy-load env (same as main.py) ─────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from agent.graph import component_agent
from agent.states import ComponentRequest
from preview import build_preview_html
from frontend.api import session_store as store

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="AngularHelp API", version="1.0.0")

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    session_id: str | None = None
    prompt: str


class GenerateResponse(BaseModel):
    session_id: str
    component_name: str
    typescript_code: str
    html_template: str
    scss_styles: str
    summary: str
    validation_passed: bool
    chat_log: list[dict]


class SessionResponse(BaseModel):
    session_id: str
    chat_log: list[dict]


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build a short LLM summary from the component
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(prompt: str, component_name: str, passed: bool) -> str:
    status = "✅ passed" if passed else "⚠️ completed with warnings"
    return f"Built '{component_name}' for '{prompt}' — validation {status}."


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest):
    """
    Generate (or iterate on) an Angular component.
    Uses session memory so follow-up prompts get full context.
    """
    session = store.get_or_create(body.session_id)

    # Build agent history before appending the new turn
    history_for_agent = list(session.conversation_history)

    # If there was a previous component, prepend it as assistant context
    if session.last_component:
        prev = session.last_component
        history_for_agent.append({
            "role": "assistant",
            "content": (
                f"Previously generated component '{prev.component_name}':\n"
                f"TypeScript:\n{prev.typescript_code}\n\nHTML:\n{prev.html_template}"
            ),
        })

    # Append the new user turn to session BEFORE invoking so history is persisted
    store.append_user_turn(session, body.prompt)

    # Build the ComponentRequest
    request = ComponentRequest(
        user_prompt=body.prompt,
        conversation_history=history_for_agent,
        current_component=None,
    )

    try:
        result = component_agent.invoke(
            {"request": request},
            {"recursion_limit": 20},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    req: ComponentRequest = result["request"]
    comp = req.final_component or req.current_component

    if not comp:
        raise HTTPException(status_code=500, detail="No component was generated.")

    # Persist for next turn
    session.last_component = comp

    summary = _build_summary(body.prompt, comp.component_name, comp.validation_passed)
    store.append_assistant_turn(session, comp.component_name, summary)

    return GenerateResponse(
        session_id=session.session_id,
        component_name=comp.component_name,
        typescript_code=comp.typescript_code,
        html_template=comp.html_template,
        scss_styles=comp.scss_styles,
        summary=summary,
        validation_passed=comp.validation_passed,
        chat_log=[
            {"role": e.role, "content": e.content, "summary": e.summary}
            for e in session.chat_log
        ],
    )


@app.get("/api/preview/{session_id}", response_class=HTMLResponse)
async def preview(session_id: str):
    """Return a ready-to-render HTML preview of the latest component in the session."""
    session = store.get_session(session_id)
    if not session or not session.last_component:
        raise HTTPException(status_code=404, detail="No component in this session yet.")

    comp = session.last_component
    html = build_preview_html(comp.component_name, comp.html_template, comp.scss_styles)
    return HTMLResponse(content=html)


@app.get("/api/session/{session_id}", response_model=SessionResponse)
async def get_session_info(session_id: str):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return SessionResponse(
        session_id=session.session_id,
        chat_log=[
            {"role": e.role, "content": e.content, "summary": e.summary}
            for e in session.chat_log
        ],
    )


@app.post("/api/reset")
async def reset(body: dict):
    """Clear a session and return a fresh session_id."""
    old_id = body.get("session_id", "")
    new_id = store.reset_session(old_id)
    return {"session_id": new_id}


@app.get("/api/new-session")
async def new_session():
    """Create a brand-new empty session."""
    sid = store.create_session()
    return {"session_id": sid}


# ─────────────────────────────────────────────────────────────────────────────
# Serve the frontend static files — MUST be last so API routes take priority
# ─────────────────────────────────────────────────────────────────────────────

_STATIC = pathlib.Path(__file__).resolve().parents[1]   # d:\coder-buddy-main\frontend
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
