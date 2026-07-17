"""Sphinx configuration for dsw-locale-tool."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "DSW Locale Tool"
copyright = "2026, depositar contributors"
author = "depositar contributors"
release = "0.1.0"
language = "zh_TW"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"
exclude_patterns = ["_build"]
html_theme = "furo"
html_title = "DSW UI 繁體中文補翻指南"
html_theme_options = {
    "source_repository": "https://github.com/ThreeMonth03/dsw-locale-tool/",
    "source_branch": "main",
    "source_directory": "docs/",
}

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3
