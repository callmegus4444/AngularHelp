"""
prompts.py — Guided Component Architect
========================================
Prompt factory functions for the Angular component pipeline:
  - load_design_system()
  - angular_generator_prompt()
  - validator_prompt()
"""

import json
import pathlib


def load_design_system() -> dict:
    """
    Loads agent/design_system.json relative to this file.
    Returns the parsed dict with 'tokens' and 'tailwind_classes' keys.
    """
    path = pathlib.Path(__file__).parent / "design_system.json"
    return json.loads(path.read_text(encoding="utf-8"))


def angular_generator_prompt(
    user_prompt: str,
    conversation_history: list = None,
    previous_errors: list = None,
) -> list:
    """
    Builds the full message list for the Angular component generator LLM call.

    Args:
        user_prompt:          What the user wants to build.
        conversation_history: Previous turns (list of role/content dicts) for
                              multi-turn session continuity.
        previous_errors:      Validation errors from the previous attempt so the
                              LLM knows exactly what to fix on this retry.

    Returns:
        A list of message dicts ready for llm.invoke().
    """
    ds = load_design_system()
    tokens_json  = json.dumps(ds["tokens"], indent=2)
    tailwind_json = json.dumps(ds["tailwind_classes"], indent=2)

    # Build the error-correction block only when retrying
    error_section = ""
    if previous_errors:
        error_lines = "\n".join(f"- {e}" for e in previous_errors)
        error_section = f"""
PREVIOUS VALIDATION ERRORS — you MUST fix ALL of these before responding:
{error_lines}
"""

    system_content = f"""You are an expert Angular component developer. Adhere to every rule below absolutely.

OUTPUT FORMAT:
  Respond ONLY with a valid JSON object.
  No markdown, no explanation, no code fences.

DESIGN SYSTEM:
  Use ONLY the colors and tokens defined below. No other colors are permitted.

FRAMEWORK:
  Generate Angular 17+ standalone components using Tailwind CSS utility classes.
  Do NOT use Angular Material — Tailwind only.

REQUIRED JSON KEYS (exactly these four, no others):
  component_name   — PascalCase name, e.g. "LoginCardComponent"
  typescript_code  — Full .component.ts file content
  html_template    — Full .component.html file content
  scss_styles      — Full .component.scss file content

───────────────────────────────────────────
DESIGN TOKENS (only these hex values allowed):
{tokens_json}

TAILWIND CLASS MAPPINGS (prefer these exact classes):
{tailwind_json}
───────────────────────────────────────────

ANGULAR COMPONENT RULES:
  TypeScript:
    - Decorator: @Component with standalone: true, selector, and templateUrl / styleUrls
    - Import CommonModule in the imports array
    - Use proper TypeScript typing throughout

  HTML:
    - Use Tailwind utility classes for all layout and spacing
    - Reference design-token colors via their exact hex values when inline styles are needed
    - Avoid unclosed tags — every opened tag must be properly closed

  SCSS:
    - Minimal: prefer Tailwind classes; only add SCSS for complex animations or glassmorphism
    - Glassmorphism effect (use when relevant):
        backdrop-filter: blur(10px);
        background: rgba(30, 41, 59, 0.7);
    - All color values in SCSS must match a design-token hex value exactly
    - Ensure all braces are balanced (every {{ must have a matching }})
{error_section}"""

    messages: list[dict] = [{"role": "system", "content": system_content}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": f"Generate an Angular component for: {user_prompt}",
    })

    return messages


def validator_prompt(component: dict, design_system: dict) -> str:
    """
    Builds the critic/validator prompt sent to the LLM as a secondary quality gate.

    Args:
        component:     Dict with keys typescript_code, html_template, scss_styles.
        design_system: The full design_system.json dict.

    Returns:
        A single string prompt. The LLM must respond with JSON only.
    """
    tokens_json = json.dumps(design_system["tokens"], indent=2)

    return f"""You are a strict Angular code validator. Analyze the component below and return ONLY a JSON object.

DESIGN SYSTEM TOKENS:
{tokens_json}

─── COMPONENT TO VALIDATE ───

TypeScript:
{component['typescript_code']}

HTML:
{component['html_template']}

SCSS:
{component['scss_styles']}

─────────────────────────────

Validation rules to check:
1. No hardcoded colors exist that are NOT in the design tokens list
   (check both HTML inline styles and SCSS rules).
2. TypeScript has a valid @Component decorator with selector and standalone: true.
3. HTML has no unclosed tags.
4. SCSS has no obvious syntax errors (unclosed braces).
5. Component uses Tailwind classes for layout (flex, grid, p-*, m-*, etc.).
6. Primary action buttons use bg-[#6366f1] or the equivalent token color.
7. Background uses #0f172a or #1e293b (surface) where applicable.

Return ONLY a JSON object with this exact structure — no explanation, no markdown:
{{
  "passed": true,
  "errors": []
}}

If any rule is violated set "passed" to false and list each violation in "errors".
"""
