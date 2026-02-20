# AngularHelp — AI-Powered Angular Component Generator

> Describe any UI component. AngularHelp generates production-quality Angular code instantly using LangGraph + Groq.

---

## What It Does

AngularHelp is an agentic pipeline that:
1. Takes a natural-language description of an Angular component
2. Generates TypeScript, HTML, and SCSS using GPT / Groq LLMs via LangGraph
3. Validates the output against a strict design system
4. Lets you view syntax-highlighted code **and** a live preview — all in a beautiful web UI

---

## Project Structure

```
AngularHelp/
├── main.py                        # Original CLI entry point
├── preview.py                     # Standalone HTML preview builder
├── pyproject.toml                 # Dependencies
├── agent/
│   ├── graph.py                   # LangGraph pipeline
│   ├── states.py                  # Pydantic state models
│   ├── prompts.py                 # LLM prompt factories
│   ├── tools.py                   # Agent tools
│   └── design_system.json         # Design tokens (colors, typography)
├── frontend/
│   ├── index.html                 # 3-panel web UI
│   ├── styles.css                 # Dark glassmorphism theme
│   ├── app.js                     # Client-side logic + session memory
│   └── api/
│       ├── server.py              # FastAPI bridge to LangGraph agent
│       └── session_store.py       # In-memory session & chat memory
└── generated_project/
    ├── components/                # Generated Angular component files
    └── previews/                  # Generated HTML preview pages
```

---

## Web UI (Recommended)

### Start the server

```powershell
cd AngularHelp
pip install fastapi "uvicorn[standard]" python-multipart
python -m uvicorn frontend.api.server:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

### How the UI works

| Panel | What it does |
|-------|-------------|
| **Center Hero** | Type what you want to build → press Enter |
| **Code Tab** | Syntax-highlighted TypeScript / HTML / SCSS with copy button |
| **Preview Tab** | Live iframe rendering the generated component |
| **Right Chat Panel** | Full build history; type follow-up prompts to iterate |

**Memory:** Every browser tab gets a UUID session. The server maintains full conversation history per session — every follow-up prompt has complete context. Click **New Session** in the nav to reset.

---

## CLI Usage (Alternative)

```powershell
python main.py
```

Commands inside the REPL:
- `<description>` — Generate an Angular component
- `new` — Start a fresh session
- `exit` — Quit

---

## Prerequisites

- Python 3.11+
- A `.env` file with your API key:

```env
GROQ_API_KEY=your_key_here
```

Install dependencies:

```powershell
pip install -r requirements.txt
# or using uv:
uv sync
```

---

## Design System

All components are constrained to a strict design system defined in `agent/design_system.json`:

| Token | Value |
|-------|-------|
| `primary-color` | `#6366f1` (Indigo) |
| `surface` | `#1e293b` |
| `bg` | `#0f172a` |
| `accent` | `#06b6d4` (Cyan) |

Components use **Tailwind CSS** utility classes and **Inter** font.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM Orchestration | LangGraph + LangChain |
| LLM Provider | Groq (`openai/gpt-oss-120b`) |
| Backend API | FastAPI + Uvicorn |
| Frontend | Vanilla HTML / CSS / JS |
| Validation | Pydantic v2 |

---

## License

MIT