"""
graph.py — Guided Component Architect
======================================
Single LangGraph pipeline for Angular component generation:

  generator  →  validator  →  corrector (on failure)  →  finalizer
                           →  finalizer (on pass / max retries)

Exported: component_agent (compiled graph)
"""

import json
import pathlib
import re

from dotenv import load_dotenv
from langchain_core.globals import set_verbose, set_debug
from langchain_groq.chat_models import ChatGroq
from langgraph.constants import END
from langgraph.graph import StateGraph

from agent.prompts import angular_generator_prompt, validator_prompt
from agent.states import AngularComponent, ComponentRequest
from agent.tools import write_file

# ─────────────────────────────────────────────────────────────────────────────
# Initialisation
# ─────────────────────────────────────────────────────────────────────────────

_ = load_dotenv()

set_debug(False)
set_verbose(False)

# Groq LLM — model stays as specified, do not change
llm = ChatGroq(model="openai/gpt-oss-120b")

# Maximum self-correction attempts before finalizing with best-effort output
MAX_RETRIES = 2


def _load_design_system() -> dict:
    """Loads design_system.json from the agent package directory."""
    path = pathlib.Path(__file__).parent / "design_system.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Node: generator
# ─────────────────────────────────────────────────────────────────────────────

def _robust_json_parse(raw: str) -> dict:
    """
    Attempts to extract and parse a JSON object from a potentially messy string.
    - Finds the first { and last }
    - Strips common unescaped control characters
    - Handles markdown blocks
    """
    text = raw.strip()
    
    # Extract content between first { and last } if present
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
        
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: strip markdown artifacts and try again
        cleaned = re.sub(r'```[a-z]*', '', text).strip()
        data = json.loads(cleaned)

    # Post-processing: If the LLM output contained escaped quotes (e.g. \"),
    # we want to ensure they are cleaned up in the final strings.
    if isinstance(data, dict):
        for key in ["typescript_code", "html_template", "scss_styles"]:
            if key in data and isinstance(data[key], str):
                # Replace literal \" with " if the LLM double-escaped
                data[key] = data[key].replace('\\"', '"')
    return data


def generator_node(state: dict) -> dict:
    """
    Calls the LLM to produce a JSON object containing the Angular component's
    TypeScript, HTML, and SCSS files.
    """
    request: ComponentRequest = state["request"]

    # Carry forward validation errors from the previous cycle (if any)
    previous_errors = None
    if request.current_component and request.current_component.validation_errors:
        previous_errors = request.current_component.validation_errors

    attempt = request.current_component.retry_count if request.current_component else 0
    print(f"\n[generator] Calling LLM... (attempt #{attempt + 1})")

    messages = angular_generator_prompt(
        user_prompt=request.user_prompt,
        conversation_history=request.conversation_history,
        previous_errors=previous_errors,
    )

    response = llm.invoke(messages)
    raw = response.content.strip()

    # Default name fallback
    fallback_name = "GeneratedComponent"
    if request.user_prompt:
        # Try to derive a name from the prompt
        match = re.search(r'([a-zA-Z0-9]+)', request.user_prompt)
        if match:
            fallback_name = match.group(0).capitalize() + "Component"

    try:
        data = _robust_json_parse(raw)
        component = AngularComponent(
            component_name=data.get("component_name", fallback_name),
            typescript_code=data.get("typescript_code", ""),
            html_template=data.get("html_template", ""),
            scss_styles=data.get("scss_styles", ""),
            retry_count=attempt,
        )
        if not data.get("typescript_code") or not data.get("html_template"):
            raise KeyError("JSON missing required code fields")
            
    except (json.JSONDecodeError, KeyError, Exception) as exc:
        print(f"[generator] ⚠️  LLM output was not valid JSON or missing keys: {exc}")
        component = AngularComponent(
            component_name=fallback_name,
            typescript_code="",
            html_template="",
            scss_styles="",
            validation_errors=[
                f"JSON Error: {str(exc)}. Focus on providing ONLY a JSON object with keys: "
                "component_name, typescript_code, html_template, scss_styles."
            ],
            retry_count=attempt,
        )

    request.current_component = component
    return {"request": request}


# ─────────────────────────────────────────────────────────────────────────────
# Node: validator
# ─────────────────────────────────────────────────────────────────────────────

def validator_node(state: dict) -> dict:
    """
    Two-layer validation:

    Layer 1 — Deterministic checks (regex / rule-based, no LLM):
      • Unauthorized hex color values not in the design token palette
      • Missing @Component decorator
      • Missing standalone: true
      • Unbalanced SCSS braces
      • Unclosed HTML tags for common elements

    Layer 2 — LLM critic (only when Layer 1 passes):
      • Semantic review against the design system via validator_prompt()

    Populates component.validation_errors, sets validation_passed,
    and increments retry_count.
    """
    request: ComponentRequest = state["request"]
    component = request.current_component
    ds = _load_design_system()
    errors: list[str] = []

    all_code = component.typescript_code + component.html_template + component.scss_styles

    # ── Layer 1a: Unauthorized color check ────────────────────────────────────
    allowed_colors = {
        v.lower()
        for v in ds["tokens"].values()
        if isinstance(v, str) and v.startswith("#")
    }
    for hex_val in re.findall(r"#([0-9a-fA-F]{3,8})\b", all_code):
        full_hex = f"#{hex_val.lower()}"
        # Expand 3-char shorthand (#fff → #ffffff) for comparison
        if len(hex_val) == 3:
            expanded = "#" + "".join(c * 2 for c in hex_val.lower())
            if full_hex not in allowed_colors and expanded not in allowed_colors:
                errors.append(f"Unauthorized color: #{hex_val} — use a design-token color")
        elif full_hex not in allowed_colors:
            errors.append(f"Unauthorized color: #{hex_val} — use a design-token color")

    # ── Layer 1b: @Component decorator checks ────────────────────────────────
    if component.typescript_code:
        if "@Component" not in component.typescript_code:
            errors.append("Missing @Component decorator in TypeScript file")
        elif "standalone: true" not in component.typescript_code:
            errors.append("@Component must include 'standalone: true'")

    # ── Layer 1c: SCSS brace balance ─────────────────────────────────────────
    if component.scss_styles:
        opens  = component.scss_styles.count("{")
        closes = component.scss_styles.count("}")
        if opens != closes:
            errors.append(
                f"SCSS syntax error: mismatched braces (open={opens}, close={closes})"
            )

    # ── Layer 1d: HTML tag balance ────────────────────────────────────────────
    if component.html_template:
        for tag in ["div", "form", "button", "span", "ul", "li", "section"]:
            opens        = len(re.findall(rf"<{tag}[\s>]", component.html_template))
            closes       = len(re.findall(rf"</{tag}>", component.html_template))
            self_closing = len(re.findall(rf"<{tag}[^>]*/>", component.html_template))
            if opens != closes + self_closing:
                errors.append(
                    f"HTML tag mismatch for <{tag}>: {opens} opened, {closes} closed"
                )

    # ── Layer 2: LLM critic (only when Layer 1 is clean) ─────────────────────
    if not errors:
        print("[validator] Layer 1 passed — running LLM critic...")
        try:
            prompt = validator_prompt(component.model_dump(), ds)
            critic_resp = llm.invoke([{"role": "user", "content": prompt}])
            critic_raw  = critic_resp.content.strip()

            if critic_raw.startswith("```"):
                critic_raw = critic_raw.split("```")[1]
                if critic_raw.startswith("json"):
                    critic_raw = critic_raw[4:]

            result = json.loads(critic_raw.strip())
            if not result.get("passed", True):
                errors.extend(result.get("errors", []))
        except Exception as exc:
            print(f"[validator] ⚠️  LLM critic call failed (non-fatal): {exc}")

    # ── Update component state ────────────────────────────────────────────────
    component.validation_errors  = errors
    component.validation_passed  = len(errors) == 0
    component.retry_count       += 1

    label = "✅ PASSED" if component.validation_passed else f"❌ FAILED ({len(errors)} errors)"
    print(f"[validator] Validation {label}")

    request.current_component = component
    return {"request": request}


# ─────────────────────────────────────────────────────────────────────────────
# Node: corrector
# ─────────────────────────────────────────────────────────────────────────────

def corrector_node(state: dict) -> dict:
    """
    Passes validation errors back to the generator for a retry.
    The actual error injection happens inside angular_generator_prompt(),
    so this node simply logs and forwards state unchanged.
    """
    request: ComponentRequest = state["request"]
    print(
        f"[corrector] Sending {len(request.current_component.validation_errors)} error(s) "
        f"back to generator (attempt {request.current_component.retry_count}/{MAX_RETRIES})"
    )
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node: finalizer
# ─────────────────────────────────────────────────────────────────────────────

def finalizer_node(state: dict) -> dict:
    """
    Writes all three component files to disk under:
      generated_project/components/{kebab-name}/{kebab-name}.component.{ext}

    Marks the request as DONE and sets final_component.
    """
    request: ComponentRequest = state["request"]
    component = request.current_component

    # PascalCase → kebab-case  (e.g. LoginCardComponent → login-card)
    name_stripped = component.component_name.replace("Component", "").strip()
    kebab_name    = re.sub(r"(?<!^)(?=[A-Z])", "-", name_stripped).lower()
    base_path     = f"components/{kebab_name}/{kebab_name}"

    print(f"\n[finalizer] Writing files to generated_project/{base_path}.*")

    write_file.run({"path": f"{base_path}.component.ts",   "content": component.typescript_code})
    write_file.run({"path": f"{base_path}.component.html", "content": component.html_template})
    write_file.run({"path": f"{base_path}.component.scss", "content": component.scss_styles})

    if not component.validation_passed:
        print("[finalizer] ⚠️  Written with remaining errors (max retries exhausted)")

    request.final_component = component
    request.status          = "DONE"
    return {"request": request}


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge: decide retry vs. finalize
# ─────────────────────────────────────────────────────────────────────────────

def should_retry(state: dict) -> str:
    """
    Returns:
        "finalize" — validation passed, or MAX_RETRIES exhausted
        "correct"  — validation failed and retries remain
    """
    request: ComponentRequest = state["request"]
    component = request.current_component

    if component.validation_passed:
        print("[router] ✅ Validation passed — finalizing.")
        return "finalize"

    if component.retry_count >= MAX_RETRIES:
        print(
            f"[router] ⚠️  Max retries ({MAX_RETRIES}) reached. "
            f"Finalizing with errors: {component.validation_errors}"
        )
        return "finalize"

    print(f"[router] 🔄 Retry {component.retry_count}/{MAX_RETRIES}.")
    return "correct"


# ─────────────────────────────────────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────────────────────────────────────

_graph = StateGraph(dict)

_graph.add_node("generator",  generator_node)
_graph.add_node("validator",  validator_node)
_graph.add_node("corrector",  corrector_node)
_graph.add_node("finalizer",  finalizer_node)

_graph.set_entry_point("generator")

_graph.add_edge("generator", "validator")
_graph.add_conditional_edges(
    "validator",
    should_retry,
    {"finalize": "finalizer", "correct": "corrector"},
)
_graph.add_edge("corrector", "generator")
_graph.add_edge("finalizer", END)

# Public export — used by main.py
component_agent = _graph.compile()
