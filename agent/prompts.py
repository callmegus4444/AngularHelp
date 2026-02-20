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
    conversation_history: list[dict] | None = None,
    previous_errors: list[str] | None = None,
) -> list[dict]:
    ds = load_design_system()
    tokens_json = json.dumps(ds["tokens"], indent=2)
    tailwind_json = json.dumps(ds["tailwind_classes"], indent=2)

    error_section = ""
    if previous_errors:
        error_lines = "\n".join(f"- {e}" for e in previous_errors)
        error_section = f"\n\nCRITICAL FIX REQUIRED (PREVIOUS FAILURE):\n{error_lines}"

    system_content = f"""You are a High-End Angular Code Architect.

GOAL: Build a premium component that follows the user's prompt while obeying the Design System.

STRICT OUTPUT RULES:
1. Respond with ONLY a single JSON object. No markdown. No text. 
2. FORMAT: {{"component_name": "...", "typescript_code": "...", "html_template": "...", "scss_styles": "..."}}
3. PROPERLY ESCAPE newlines and quotes inside code strings.

DESIGN SYSTEM (STRICT GOVERNANCE):
Use ONLY these hex colors for background, text, borders, and buttons:
{tokens_json}

Preferred Tailwind utility classes:
{tailwind_json}

VISUAL EXCELLENCE GUIDELINES (LOVABLE/BOLT.NEW QUALITY):
- Spacing: Use generous padding (p-6 to p-12) and margins. No cramped layouts.
- Depth: Use 'shadow-[0_8px_32px_rgba(0,0,0,0.3)]' and 'backdrop-blur-md' for a layered feel.
- Typography: Use font-['Inter'] for everything. Headers should be text-xl or 2xl.
- Corners: Use 'rounded-[16px]' for large containers and 'rounded-[8px]' for buttons.
- Hover: Always add 'transition-all duration-300 hover:scale-[1.02]' to interactive elements.
- Layout: If multi-item (like payment cards), use a grid or flex-col with gap-4.

ANGULAR RULES:
- Standalone components (v17+).
- Use `CommonModule` for directives like `*ngIf` or `*ngFor`.
- If no color is specified by user, default to 'primary-color' (#6366f1) or 'surface' (#1e293b).

{error_section}"""

    messages: list[dict] = [{"role": "system", "content": system_content}]
    if conversation_history:
        messages.extend(conversation_history)
    
    messages.append({"role": "user", "content": f"Generate a premium component for: {user_prompt}"})
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
