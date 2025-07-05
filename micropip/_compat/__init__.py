import sys

from .compatibility_layer import CompatibilityLayer

compatibility_layer: type[CompatibilityLayer]

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from ._compat_in_pyodide import CompatibilityInPyodide

    compatibility_layer = CompatibilityInPyodide
else:
    from ._compat_not_in_pyodide import CompatibilityNotInPyodide

    compatibility_layer = CompatibilityNotInPyodide

install = compatibility_layer.install

LOCKFILE_INFO = compatibility_layer.lockfile_info

LOCKFILE_PACKAGES = compatibility_layer.lockfile_packages

lockfile_base_url = compatibility_layer.lockfile_base_url

fetch_bytes = compatibility_layer.fetch_bytes

fetch_string_and_headers = compatibility_layer.fetch_string_and_headers

loadedPackages = compatibility_layer.loadedPackages

loadPackage = compatibility_layer.loadPackage

to_js = compatibility_layer.to_js

__all__ = [
    "LOCKFILE_INFO",
    "LOCKFILE_PACKAGES",
    "install",
    "fetch_bytes",
    "fetch_string_and_headers",
    "loadedPackages",
    "loadPackage",
    "to_js",
    "lockfile_base_url",
]
