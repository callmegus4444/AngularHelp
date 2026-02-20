"""
install_tailwind.py — AngularHelp
==================================
Automates the creation of a real Angular workspace with Tailwind CSS 
pre-configured, so you can actually run and build your components.

Usage:
    python install_tailwind.py
"""

import os
import subprocess
import sys
import pathlib

def run_command(cmd: str, cwd: str = None):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: Command failed with exit code {result.returncode}")
        sys.exit(1)

def main():
    root = pathlib.Path(__file__).parent
    project_name = "angular-workspace"
    workspace_path = root / project_name

    print("--- Angular + Tailwind Environment Setup ---")

    # 1. Check for node/npm
    try:
        subprocess.run("node -v", shell=True, capture_output=True, check=True)
        subprocess.run("npm -v", shell=True, capture_output=True, check=True)
    except:
        print("Error: Node.js and npm are required but not found in PATH.")
        return

    # 2. Create Angular Workspace if it doesn't exist
    if not workspace_path.exists():
        print(f"\n[1/4] Creating new Angular workspace: {project_name}...")
        # Use npx to avoid requiring global ng install
        run_command(f"npx -y @angular/cli@latest new {project_name} --defaults --style=scss --routing=false --skip-git", cwd=str(root))
    else:
        print(f"\n[1/4] Workspace '{project_name}' already exists. Skipping creation.")

    # 3. Install Tailwind CSS
    print("\n[2/4] Installing Tailwind CSS via npm...")
    run_command("npm install -D tailwindcss postcss autoprefixer", cwd=str(workspace_path))
    run_command("npx tailwindcss init", cwd=str(workspace_path))

    # 4. Configure tailwind.config.js
    print("\n[3/4] Configuring tailwind.config.js...")
    config_content = """/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      colors: {
        primary:   '#6366f1',
        'primary-hover': '#4f46e5',
        accent:    '#06b6d4',
        surface:   '#1e293b',
        bg:        '#0f172a',
      }
    },
  },
  plugins: [],
}
"""
    (workspace_path / "tailwind.config.js").write_text(config_content)

    # 5. Add Tailwind directives to styles.scss
    print("\n[4/4] Adding Tailwind directives to styles.scss...")
    styles_path = workspace_path / "src" / "styles.scss"
    tailwind_directives = """@tailwind base;
@tailwind components;
@tailwind utilities;

// Custom design system variables (optional but helpful)
:root {
  --primary: #6366f1;
  --accent: #06b6d4;
  --bg: #0f172a;
}

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: var(--bg);
  color: white;
}
"""
    styles_path.write_text(tailwind_directives)

    print("\n" + "="*50)
    print("✅  Angular + Tailwind setup COMPLETE!")
    print("="*50)
    print(f"\nYour workspace is at: {workspace_path}")
    print("\nNext steps:")
    print(f"  1. cd {project_name}")
    print(f"  2. Copy your generated component files into src/app/")
    print(f"  3. Run: npm start")
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
