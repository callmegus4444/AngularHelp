"""
main.py — Guided Component Architect
======================================
Interactive CLI entry point for the Angular component generation pipeline.

Usage:
    python main.py

Session commands:
    <description>   Generate an Angular component
    new             Start a fresh session (clears conversation history)
    exit            Quit the program

Multi-turn editing is supported: after a component is generated you can
describe follow-up changes (e.g. "make the button rounded") and the previous
component context is passed back to the LLM automatically.
"""

import sys
import traceback

from agent.graph import component_agent
from agent.states import ComponentRequest


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def display_result(request: ComponentRequest) -> None:
    """
    Prints a concise summary of the generated component to stdout.

    Shows the component name, validation status, any remaining errors,
    and a preview of each generated file (first 500 chars of TS and HTML,
    first 300 chars of SCSS).
    """
    comp = request.final_component or request.current_component
    if not comp:
        print("[ No component was generated. ]")
        return

    divider = "=" * 60
    print(f"\n{divider}")
    print(f"  Component : {comp.component_name}")

    if comp.validation_passed:
        print("  Validation: ✅ PASSED")
    else:
        print("  Validation: ⚠️  FAILED (finalized after max retries)")
        for err in comp.validation_errors:
            print(f"    • {err}")

    print(f"\n--- TypeScript (.component.ts) ---")
    print(comp.typescript_code[:500] + ("..." if len(comp.typescript_code) > 500 else ""))

    print(f"\n--- HTML (.component.html) ---")
    print(comp.html_template[:500] + ("..." if len(comp.html_template) > 500 else ""))

    print(f"\n--- SCSS (.component.scss) ---")
    print(comp.scss_styles[:300] + ("..." if len(comp.scss_styles) > 300 else ""))

    print(f"\n  Files written to: generated_project/components/")
    print(divider)


# ─────────────────────────────────────────────────────────────────────────────
# Main CLI loop
# ─────────────────────────────────────────────────────────────────────────────

def run() -> None:
    """
    Interactive REPL that drives the component_agent pipeline.

    State management:
      - request:  The most recently completed ComponentRequest; None at session start.
      - history:  Multi-turn conversation messages list; cleared on 'new'.
    """
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║              AngularHelp  (v1.0)                    ║")
    print("║  Powered by LangGraph + Groq (openai/gpt-oss-120b)  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("Describe an Angular component to generate it.")
    print("Commands:  'new' — start fresh session | 'exit' — quit")
    print()

    request: ComponentRequest | None = None
    history: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Graceful exit on Ctrl-C / Ctrl-D
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ── Built-in commands ──────────────────────────────────────────────────
        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        if user_input.lower() == "new":
            request = None
            history = []
            print("\n[ New session started — conversation history cleared. ]\n")
            continue

        # ── Append the previous component to history for context continuity ───
        if request and request.final_component:
            prev_ts   = request.final_component.typescript_code
            prev_html = request.final_component.html_template
            history.append({
                "role": "assistant",
                "content": (
                    f"Previously generated component '{request.final_component.component_name}':\n"
                    f"TypeScript:\n{prev_ts}\n\nHTML:\n{prev_html}"
                ),
            })

        # Current user turn (added before invoking so it becomes part of history)
        history.append({"role": "user", "content": user_input})

        # Build a fresh ComponentRequest for this turn, carrying conversation history
        new_request = ComponentRequest(
            user_prompt=user_input,
            # Pass history EXCLUDING the current user turn (already in user_prompt)
            conversation_history=history[:-1],
            current_component=None,
        )

        print("\nGenerating...\n")
        try:
            result = component_agent.invoke(
                {"request": new_request},
                {"recursion_limit": 20},
            )
        except Exception:
            traceback.print_exc()
            print("\n[ERROR] Pipeline failed. Try again or type 'new' to reset.\n")
            continue

        # Unpack result and display
        request = result["request"]
        display_result(request)

        # Append the assistant's summary to history for the next turn
        if request.final_component:
            history.append({
                "role": "assistant",
                "content": f"Generated {request.final_component.component_name} successfully.",
            })

        print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run()