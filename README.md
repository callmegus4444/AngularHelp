# AngularHelp

An AI-powered Angular component generator built with **LangGraph** and **Groq** (`openai/gpt-oss-120b`). Transforms natural language descriptions into valid, styled Angular components that strictly follow a predefined design system.

Features a **2-layer validator** (regex + LLM critic), a **self-correction loop** (up to 2 retries), and an instant **browser preview** tool — no Angular CLI needed.

---

## Agentic Loop Architecture

```
User Prompt
    │
    ▼
┌─────────────┐
│  generator  │◄──────────────────────┐
│   (node)    │                       │
└──────┬──────┘                       │
       │ Angular Component JSON        │
       ▼                              │
┌─────────────┐    errors remain      │
│  validator  │──── & retries left ──►│
│   (node)    │                       │
└──────┬──────┘                       │
       │ passed / max retries reached  │
       ▼                              │
┌─────────────┐                  ┌────┴────────┐
│  finalizer  │                  │  corrector  │
│   (node)    │                  │   (node)    │
└──────┬──────┘                  └─────────────┘
       │
       ▼
  Files on disk
```

### Node Descriptions

| Node | Responsibility |
|---|---|
| **generator** | Calls the LLM with the user prompt (plus previous error context on retries) to produce a JSON object containing the Angular TypeScript, HTML, and SCSS files. |
| **validator** | Runs two layers of checks: (1) deterministic regex/rule checks — unauthorized colors, missing `@Component`, missing `standalone: true`, SCSS brace balance, HTML tag mismatches; (2) if layer 1 passes, a secondary LLM critic call performs a semantic review against the design system. |
| **corrector** | If validation fails and retries remain, passes the error list back to the generator node for a corrective re-run with the errors injected into the prompt. |
| **finalizer** | Writes the three component files to disk under `generated_project/components/{component-name}/` and marks the request as `DONE`. |

`MAX_RETRIES` is set to `2` in `agent/graph.py`. If all retries are exhausted the best available output is written to disk with a warning.

---

## Design System

Design tokens and Tailwind class mappings live in `agent/design_system.json`. All generated components must use **only** the colors, border radii, fonts, and shadows defined there. The validator enforces this automatically on every generation.

| Token | Value |
|---|---|
| primary-color | `#6366f1` |
| primary-hover | `#4f46e5` |
| accent-color | `#06b6d4` |
| error-color | `#ef4444` |
| success-color | `#22c55e` |
| background | `#0f172a` |
| surface | `#1e293b` |
| text-primary | `#f8fafc` |
| text-secondary | `#94a3b8` |

---

## Multi-Turn Editing

The CLI supports follow-up prompts within the same session. After a component is generated you can say things like:

- *"now make the button rounded"*
- *"add a loading spinner"*
- *"change the background to the surface color"*

The previous component context is automatically passed back to the LLM. Type `new` to start a fresh session.

---

## Project Structure

```
coder-buddy-main/
├── agent/
│   ├── design_system.json     # Design tokens & Tailwind class mappings
│   ├── graph.py               # LangGraph pipeline (generator→validator→corrector→finalizer)
│   ├── prompts.py             # LLM prompt factories
│   ├── states.py              # Pydantic models (AngularComponent, ComponentRequest)
│   └── tools.py               # write_file, read_file, list_files helpers
├── generated_project/
│   ├── components/            # Generated Angular component source files
│   │   └── {component-name}/
│   │       ├── {name}.component.ts
│   │       ├── {name}.component.html
│   │       └── {name}.component.scss
│   └── previews/              # Standalone browser-ready preview HTML files
│       └── {name}.preview.html
├── main.py                    # Interactive CLI entry point
├── preview.py                 # Browser preview generator
└── pyproject.toml
```

---

---

## Previewing Generated Components

After generating a component with `python main.py`, instantly preview it in the browser:

```bash
# Open a component preview in the default browser
python preview.py login-card

# List all components available to preview
python preview.py

# Build the preview HTML without auto-opening the browser
python preview.py login-card --no-open
```

Preview files are saved to `generated_project/previews/` as standalone `.html` files — double-click any of them in File Explorer to view offline.

> [!NOTE]
> The preview script injects the **Tailwind CDN**, converts SCSS variables to plain CSS, and strips Angular-specific template syntax (`*ngIf`, `[(ngModel)]`, `{{ }}`), so the visual layout renders faithfully in any browser without Angular CLI.

---

## Setup

Make sure you have `uv` installed. Then:

```bash
uv venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

uv pip install -r pyproject.toml
```

Create a `.env` file and add:

```
GROQ_API_KEY=your_groq_api_key_here
```

Start the application:

```bash
python main.py
```

---

## Example Prompts

- A login card with a glassmorphism effect
- A dashboard stats widget with 4 metric cards
- A signup form with email, password, and validation error states
- A navigation sidebar with icons and active state highlighting
- A modal dialog for confirming a delete action
- A data table component with sortable columns and pagination

---

## Assumptions

> [!NOTE]
> Tailwind CSS is assumed to be pre-configured in the target Angular project environment. The generator outputs Tailwind utility classes but does not scaffold a full Angular workspace. Copy the generated files from `generated_project/components/` into your existing Angular project.

---

## Legacy Pipeline

The original **Coder Buddy** planner → architect → coder pipeline is still available in `agent/graph.py` as the compiled `agent` object for full backward compatibility.