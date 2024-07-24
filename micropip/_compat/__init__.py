import sys

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from ._compat_in_pyodide import (
        CompatibilityInPyodide as CompatibilityLayer,
    )
else:
    from ._compat_not_in_pyodide import (
        CompatibilityNotInPyodide as CompatibilityLayer,
    )

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
]
