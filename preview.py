"""
preview.py — AngularHelp
=========================
Generates a standalone HTML preview of any component in generated_project/components/.

Usage:
    python preview.py                  # lists available components
    python preview.py login-card       # opens the login-card preview in browser
    python preview.py login-card --no-open   # generates HTML but does not open browser
"""

import argparse
import json
import pathlib
import re
import webbrowser

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT        = pathlib.Path(__file__).parent
COMPONENTS  = ROOT / "generated_project" / "components"
PREVIEWS    = ROOT / "generated_project" / "previews"
DS_PATH     = ROOT / "agent" / "design_system.json"


def load_design_system() -> dict:
    return json.loads(DS_PATH.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# HTML template builder
# ─────────────────────────────────────────────────────────────────────────────

def build_preview_html(name: str, html_template: str, scss_styles: str) -> str:
    """
    Wraps an Angular component's HTML template in a standalone preview page.
    - Tailwind CDN handles utility classes
    - SCSS is converted to vanilla CSS (interpolations stripped, vars inlined)
    - Design system tokens are injected as CSS custom properties
    - Angular-specific syntax (*ngIf, @for, [(ngModel)] etc.) is stripped
      so the layout renders faithfully in plain HTML
    """
    ds     = load_design_system()
    tokens = ds["tokens"]

    # ── CSS custom properties from design tokens ───────────────────────────────
    css_vars = "\n".join(
        f"  --{k}: {v};"
        for k, v in tokens.items()
    )

    # ── Light SCSS → CSS conversion ───────────────────────────────────────────
    css = scss_styles

    # Replace SCSS variable declarations ($name: value;) with nothing
    # and inline their values where used
    scss_vars: dict[str, str] = {}
    for m in re.finditer(r"\$([a-zA-Z0-9_-]+)\s*:\s*([^;]+);", css):
        scss_vars[m.group(1)] = m.group(2).strip()

    # Remove variable declarations
    css = re.sub(r"\$[a-zA-Z0-9_-]+\s*:[^;]+;", "", css)

    # Inline variable usages  (rgba($surface, 0.7) → rgba(#1e293b, 0.7))
    for var, val in scss_vars.items():
        css = css.replace(f"${var}", val)

    # Convert rgba(#hex, alpha) → rgba(r,g,b,alpha) for browser compatibility
    def hex_to_rgba(m: re.Match) -> str:
        hex_color = m.group(1).lstrip("#")
        alpha     = m.group(2)
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    css = re.sub(r"rgba\(#([0-9a-fA-F]{3,6}),\s*([^)]+)\)", hex_to_rgba, css)

    # Remove SCSS nesting ampersand shortcuts not valid in plain CSS
    css = re.sub(r"&:", ":", css)

    # ── Strip Angular template syntax from HTML ────────────────────────────────
    html = html_template

    # Remove structural directives: *ngIf, *ngFor, @if, @for, @switch, @case
    html = re.sub(r'\s*\*ngIf="[^"]*"', "", html)
    html = re.sub(r'\s*\*ngFor="[^"]*"', "", html)
    html = re.sub(r'@if\s*\([^)]*\)\s*\{', "", html)
    html = re.sub(r'@for\s*\([^)]*\)\s*\{', "", html)
    html = re.sub(r'@empty\s*\{', "", html)
    html = re.sub(r'@switch\s*\([^)]*\)\s*\{', "", html)
    html = re.sub(r'@case\s*\([^)]*\)\s*\{', "", html)
    html = re.sub(r'@default\s*\{', "", html)
    html = re.sub(r'\}', "", html)  # closing braces from @-blocks

    # Strip two-way bindings, event bindings, property bindings
    html = re.sub(r'\s*\[\(ngModel\)\]="[^"]*"', "", html)
    html = re.sub(r'\s*\(ngSubmit\)="[^"]*"', "", html)
    html = re.sub(r'\s*\([a-zA-Z]+\)="[^"]*"', "", html)
    html = re.sub(r'\s*\[[a-zA-Z]+\]="[^"]*"', "", html)

    # Strip Angular interpolation {{ expr }} — leave placeholder text
    html = re.sub(r"\{\{[^}]*\}\}", "…", html)

    # ── Assemble final preview page ───────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Preview — {name}</title>

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    // Configure Tailwind to allow arbitrary values used by the design system
    tailwind.config = {{
      theme: {{
        extend: {{
          fontFamily: {{ Inter: ['Inter', 'sans-serif'] }},
          colors: {{
            primary:   '#6366f1',
            'primary-hover': '#4f46e5',
            accent:    '#06b6d4',
            surface:   '#1e293b',
            bg:        '#0f172a',
          }},
        }},
      }},
    }};
  </script>

  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    rel="stylesheet"
  />

  <style>
    /* Design system CSS custom properties */
    :root {{
{css_vars}
    }}

    /* Component SCSS (converted to plain CSS) */
{css}

    /* Preview chrome */
    body {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      background-color: #0f172a;
      font-family: 'Inter', sans-serif;
      padding: 16px;
    }}

    .preview-banner {{
      width: 100%;
      max-width: 800px;
      background: rgba(99,102,241,0.15);
      border: 1px solid rgba(99,102,241,0.3);
      border-radius: 8px;
      padding: 8px 16px;
      margin-bottom: 40px;
      color: #94a3b8;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .preview-banner span.dot {{
      width: 8px; height: 8px;
      background: #22c55e;
      border-radius: 50%;
      display: inline-block;
    }}

    .preview-area {{
      width: 100%;
      max-width: 800px;
      display: flex;
      justify-content: center;
    }}
  </style>
</head>
<body>
  <div class="preview-banner">
    <span class="dot"></span>
    AngularHelp Preview &mdash; <strong style="color:#f8fafc">{name}</strong>
    &nbsp;&bull;&nbsp; Design system tokens applied &nbsp;&bull;&nbsp; Angular syntax stripped
  </div>

  <div class="preview-area">
    {html}
  </div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def list_components() -> list[str]:
    if not COMPONENTS.exists():
        return []
    return sorted(p.name for p in COMPONENTS.iterdir() if p.is_dir())


def generate_preview(component_name: str, open_browser: bool = True) -> pathlib.Path:
    comp_dir = COMPONENTS / component_name
    if not comp_dir.exists():
        raise FileNotFoundError(
            f"Component '{component_name}' not found in {COMPONENTS}. "
            f"Available: {list_components()}"
        )

    # Read generated files
    html_file = comp_dir / f"{component_name}.component.html"
    scss_file = comp_dir / f"{component_name}.component.scss"

    html_content = html_file.read_text(encoding="utf-8") if html_file.exists() else "<p>No HTML template found.</p>"
    scss_content = scss_file.read_text(encoding="utf-8") if scss_file.exists() else ""

    # Build the preview HTML
    preview_html = build_preview_html(component_name, html_content, scss_content)

    # Write to previews directory
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    out_path = PREVIEWS / f"{component_name}.preview.html"
    out_path.write_text(preview_html, encoding="utf-8")

    print(f"✅  Preview generated: {out_path}")

    if open_browser:
        webbrowser.open(out_path.as_uri())
        print("🌐  Opened in default browser.")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AngularHelp — Preview a generated Angular component",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python preview.py login-card",
    )
    parser.add_argument(
        "component",
        nargs="?",
        help="Kebab-case component name (e.g. login-card). Omit to list all.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Generate the preview HTML but do not open the browser automatically.",
    )
    args = parser.parse_args()

    if not args.component:
        available = list_components()
        if not available:
            print("No components generated yet. Run  python main.py  first.")
        else:
            print("Available components:")
            for name in available:
                print(f"  • {name}")
            print("\nUsage:  python preview.py <component-name>")
        return

    try:
        generate_preview(args.component, open_browser=not args.no_open)
    except FileNotFoundError as exc:
        print(f"❌  {exc}")


if __name__ == "__main__":
    main()
