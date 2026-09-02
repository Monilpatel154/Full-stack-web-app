#!/usr/bin/env python3
"""
Adds the new animated SVG favicon link to every HTML page in the LADLI
site/ folder, in place. Safe to run more than once.

Usage:
    1. Put this script inside your LADLI folder (same level as "site").
    2. Run:  python3 apply_favicon_update.py
"""
import glob
import os

SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

OLD_BLOCK = '''    <link rel="icon" type="image/png" sizes="32x32" href="assets/images/favicon-32.png" />
    <link rel="icon" type="image/png" sizes="16x16" href="assets/images/favicon-16.png" />
    <link rel="apple-touch-icon" href="assets/images/favicon-180.png" />
    <link rel="icon" href="assets/images/favicon.ico" />'''

NEW_BLOCK = '''    <link rel="icon" type="image/svg+xml" href="assets/images/favicon.svg" />
    <link rel="icon" type="image/png" sizes="32x32" href="assets/images/favicon-32.png" />
    <link rel="icon" type="image/png" sizes="16x16" href="assets/images/favicon-16.png" />
    <link rel="apple-touch-icon" href="assets/images/favicon-180.png" />
    <link rel="icon" href="assets/images/favicon.ico" />'''

def main():
    if not os.path.isdir(SITE_DIR):
        print(f"Could not find a 'site' folder next to this script at: {SITE_DIR}")
        print("Move this script into your LADLI project folder and try again.")
        return

    changed, already_done, skipped = [], [], []

    for path in glob.glob(os.path.join(SITE_DIR, "*.html")):
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if 'favicon.svg' in content:
            already_done.append(name)
        elif OLD_BLOCK in content:
            content = content.replace(OLD_BLOCK, NEW_BLOCK)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            changed.append(name)
        elif "favicon" in content:
            skipped.append(name)

    print(f"Updated: {len(changed)} file(s)")
    for n in changed:
        print(f"   {n}")
    if already_done:
        print(f"Already up to date: {len(already_done)} file(s)")
    if skipped:
        print(f"Skipped (favicon markup didn't match expected pattern): {skipped}")

if __name__ == "__main__":
    main()
