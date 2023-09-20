from io import BytesIO
from typing import IO
from urllib.parse import urlparse

from pyodide._package_loader import get_dynlibs, wheel_dist_info_dir
from pyodide.ffi import IN_BROWSER, to_js
from pyodide.http import pyfetch

try:
    import pyodide_js
    from js import Object
    from pyodide_js import loadedPackages, loadPackage
    from pyodide_js._api import loadBinaryFile, loadDynlib  # type: ignore[import]

    REPODATA_PACKAGES = pyodide_js._api.repodata_packages.to_py()
    REPODATA_INFO = pyodide_js._api.repodata_info.to_py()
except ImportError:
    if IN_BROWSER:
        raise
    # Otherwise, this is pytest test collection so let it go.


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> IO[bytes]:
    parsed_url = urlparse(url)
    if parsed_url.scheme == "emfs":
        return open(parsed_url.path, "rb")
    if parsed_url.scheme == "file":
        result_bytes = (await loadBinaryFile(parsed_url.path)).to_bytes()
    else:
        result_bytes = await (await pyfetch(url, **kwargs)).bytes()
    return BytesIO(result_bytes)


async def fetch_string_and_headers(
    url: str, kwargs: dict[str, str]
) -> tuple[str, dict[str, str]]:
    response = await pyfetch(url, **kwargs)

    content = await response.string()
    # TODO: replace with response.headers when pyodide>= 0.24 is released
    headers: dict[str, str] = Object.fromEntries(
        response.js_response.headers.entries()
    ).to_py()

    return content, headers


__all__ = [
    "fetch_bytes",
    "fetch_string_and_headers",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadDynlib",
    "loadPackage",
    "get_dynlibs",
    "wheel_dist_info_dir",
    "to_js",
]
