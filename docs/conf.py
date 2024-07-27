import os
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path

project = "micropip"
copyright = "2019-2022, Pyodide contributors and Mozilla"
# author = "Pyodide Authors"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_autodoc_typehints",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.10", None),
    "pyodide": ("https://pyodide.org/en/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".*"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

html_css_files = [
    "css/pyodide.css",
]

html_theme = "sphinx_book_theme"
html_logo = "_static/img/pyodide-logo.png"
html_static_path = ["_static"]


sys.path.append(Path(__file__).parent.parent.as_posix())


try:
    release = importlib_metadata.version("micropip")
except importlib_metadata.PackageNotFoundError:
    print("Could not find package version, please install micropip to build docs")
    release = "0.0.0"

version = release
