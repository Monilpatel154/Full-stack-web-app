#!/usr/bin/env python3
"""
Installs the favicon-animation + number-of-samples fixes into your LADLI
project automatically. Does NOT delete anything — it only adds new files
and overwrites the specific files that changed.

Usage:
    1. Download "site-fixes.zip" (from the chat) into your LADLI folder
       (the same folder that already contains app.py, site/, admin/, etc.)
    2. Put this script in that same LADLI folder, next to the zip.
    3. Open a terminal there and run:
           python install_site_fixes.py
       (use "py install_site_fixes.py" if "python" isn't recognized)
"""
import os
import shutil
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(PROJECT_DIR, "site-fixes.zip")
EXTRACT_DIR = os.path.join(PROJECT_DIR, "_site-fixes-extracted")
SITE_DIR = os.path.join(PROJECT_DIR, "site")


def main():
    if not os.path.isdir(SITE_DIR):
        print(f"Could not find a 'site' folder next to this script at: {SITE_DIR}")
        print("Make sure this script is inside your LADLI project folder.")
        return

    if not os.path.isfile(ZIP_PATH):
        print(f"Could not find site-fixes.zip at: {ZIP_PATH}")
        print("Download it from the chat and put it in this same folder first.")
        return

    # 1. Unzip fresh each run
    if os.path.isdir(EXTRACT_DIR):
        shutil.rmtree(EXTRACT_DIR)
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

    fixes_root = os.path.join(EXTRACT_DIR, "site-fixes")

    copied = []

    # 2. enhance.js -> site/assets/enhance.js
    src = os.path.join(fixes_root, "enhance.js")
    dst = os.path.join(SITE_DIR, "assets", "enhance.js")
    shutil.copy2(src, dst)
    copied.append("assets/enhance.js")

    # 3. request-quote.html -> site/request-quote.html
    src = os.path.join(fixes_root, "request-quote.html")
    dst = os.path.join(SITE_DIR, "request-quote.html")
    shutil.copy2(src, dst)
    copied.append("request-quote.html")

    # 4. favicon-frames/* -> site/assets/images/favicon-frames/
    src_dir = os.path.join(fixes_root, "images", "favicon-frames")
    dst_dir = os.path.join(SITE_DIR, "assets", "images", "favicon-frames")
    if os.path.isdir(dst_dir):
        shutil.rmtree(dst_dir)  # clear out any older frame set first
    os.makedirs(dst_dir, exist_ok=True)
    for name in os.listdir(src_dir):
        shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
    copied.append(f"assets/images/favicon-frames/ ({len(os.listdir(src_dir))} frames)")

    # 5. html/*.html -> site/*.html  (overwrite each matching page)
    html_dir = os.path.join(fixes_root, "html")
    page_count = 0
    for name in os.listdir(html_dir):
        shutil.copy2(os.path.join(html_dir, name), os.path.join(SITE_DIR, name))
        page_count += 1
    copied.append(f"{page_count} page(s) in site/*.html")

    # cleanup
    shutil.rmtree(EXTRACT_DIR)

    print("Done. Installed:")
    for c in copied:
        print(f"   - {c}")
    print("\nNothing else in your project was touched or deleted.")
    print("Now restart the server and hard-refresh (close the tab fully for the favicon).")


if __name__ == "__main__":
    main()
