import sys

from .compatibility_layer import CompatibilityLayer

compatibility_layer: type[CompatibilityLayer] | None = None

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from ._compat_in_pyodide import CompatibilityInPyodide

    compatibility_layer = CompatibilityInPyodide
else:
    from ._compat_not_in_pyodide import CompatibilityNotInPyodide

    compatibility_layer = CompatibilityNotInPyodide


REPODATA_INFO = compatibility_layer.repodata_info()

REPODATA_PACKAGES = compatibility_layer.repodata_packages()

fetch_bytes = compatibility_layer.fetch_bytes

fetch_string_and_headers = compatibility_layer.fetch_string_and_headers

loadedPackages = compatibility_layer.loadedPackages

loadDynlibsFromPackage = compatibility_layer.loadDynlibsFromPackage

loadPackage = compatibility_layer.loadPackage

get_dynlibs = compatibility_layer.get_dynlibs

to_js = compatibility_layer.to_js

HttpStatusError = compatibility_layer.HttpStatusError


__all__ = [
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "fetch_bytes",
    "fetch_string_and_headers",
    "loadedPackages",
    "loadDynlibsFromPackage",
    "loadPackage",
    "get_dynlibs",
    "to_js",
    "HttpStatusError",
]
