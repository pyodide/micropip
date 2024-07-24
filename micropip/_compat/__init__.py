import sys

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from ._compat_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string_and_headers,
        get_dynlibs,
        loadDynlibsFromPackage,
        loadedPackages,
        loadPackage,
        to_js,
    )
else:
    from ._compat_not_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string_and_headers,
        get_dynlibs,
        loadDynlibsFromPackage,
        loadedPackages,
        loadPackage,
        to_js,
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
