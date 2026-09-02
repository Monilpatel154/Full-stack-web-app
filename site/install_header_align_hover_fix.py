#!/usr/bin/env python
"""
LADLI - Header alignment + radiant-pink hover fix installer
-------------------------------------------------------------
What this does:
  1. Backs up your current site/assets/styles.css (adds a .bak-TIMESTAMP copy)
  2. Copies the updated styles.css from this package into site/assets/

What changed in styles.css:
  - Header (.nav-wrap) now spreads wider on desktop screens (>1120px),
    so the logo sits further left and the phone number / Request a
    Quote button sit further right - matching the "aligned" look.
    (Mobile/tablet layout is untouched.)
  - Nav links ("Home", "About Us", "Services", etc.) now smoothly
    shift into a radiant pink/blue/orange gradient with a soft pink
    glow whenever the cursor hovers over them (and on the active page
    link), using the site's existing brand colors.

Usage:
  1. Place this script in the same folder as your project root
     (the folder that contains "site/").
  2. Run:  python install_header_align_hover_fix.py
     (or:  py install_header_align_hover_fix.py   on Windows)
  3. Restart your local server (run.bat) to see the change locally.
  4. When ready, upload site/assets/styles.css to PythonAnywhere and
     click "Reload" on the Web tab.
"""

import os
import shutil
import sys
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_CSS = os.path.join(SCRIPT_DIR, "header_align_hover_fix", "styles.css")


def find_project_root():
    """Look for a 'site' folder containing assets/styles.css, starting from
    the script's directory and checking common locations."""
    candidates = [
        SCRIPT_DIR,
        os.path.join(SCRIPT_DIR, ".."),
    ]
    for base in candidates:
        for root, dirs, files in os.walk(base):
            # avoid walking too deep / into the fix package itself
            if "header_align_hover_fix" in root:
                continue
            if os.path.basename(root) == "assets" and "styles.css" in files:
                parent = os.path.dirname(root)
                if os.path.basename(parent) == "site":
                    return parent
    return None


def main():
    if not os.path.isfile(SOURCE_CSS):
        print("ERROR: Could not find bundled styles.css at:")
        print("  " + SOURCE_CSS)
        print("Make sure this script sits next to the 'header_align_hover_fix' folder.")
        sys.exit(1)

    site_dir = find_project_root()
    if not site_dir:
        print("Could not auto-locate your 'site' folder.")
        site_dir = input("Please paste the full path to your 'site' folder: ").strip().strip('"')

    target_css = os.path.join(site_dir, "assets", "styles.css")

    if not os.path.isfile(target_css):
        print(f"ERROR: Could not find {target_css}")
        print("Please double check the path and try again.")
        sys.exit(1)

    # Backup existing file
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target_css + f".bak-{timestamp}"
    shutil.copy2(target_css, backup_path)
    print(f"Backed up existing styles.css -> {backup_path}")

    # Install new file
    shutil.copy2(SOURCE_CSS, target_css)
    print(f"Installed updated styles.css -> {target_css}")

    print("\nDone! Changes applied:")
    print("  - Header logo pulled left / phone+CTA pulled right on desktop")
    print("  - Nav links glow radiant pink-gradient on hover / active page")
    print("\nNext steps:")
    print("  1. Run your local server (run.bat) and check the header.")
    print("  2. Upload site/assets/styles.css to PythonAnywhere and click Reload.")


if __name__ == "__main__":
    main()
