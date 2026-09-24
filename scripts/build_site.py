#!/usr/bin/env python3
"""Create the public GitHub Pages artifact without private workbench state."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir()

for filename in ["index.html", "app.js", "app.css", "prototype.js", "prototype.css", "ATTRIBUTIONS.md"]:
    shutil.copy2(ROOT / filename, DIST / filename)

shutil.copytree(ROOT / "design", DIST / "design")
shutil.copytree(ROOT / "data", DIST / "data")
(DIST / ".nojekyll").write_text("", encoding="utf-8")

print(DIST)
