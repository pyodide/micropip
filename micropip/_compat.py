from pyodide._core import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string,
        get_dynlibs,
        loadDynlib,
        loadedPackages,
        loadPackage,
        to_js,
        wheel_dist_info_dir,
    )
else:
    from ._compat_not_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string,
        get_dynlibs,
        loadDynlib,
        loadedPackages,
        loadPackage,
        to_js,
        wheel_dist_info_dir,
    )

__all__ = [
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "fetch_bytes",
    "fetch_string",
    "loadedPackages",
    "loadDynlib",
    "loadPackage",
    "get_dynlibs",
    "wheel_dist_info_dir",
    "to_js",
]
