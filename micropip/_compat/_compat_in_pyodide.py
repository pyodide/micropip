from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass

from pyodide._package_loader import get_dynlibs
from pyodide.ffi import IN_BROWSER, to_js
from pyodide.http import HttpStatusError, pyfetch

from .compatibility_layer import CompatibilityLayer

try:
    import pyodide_js
    from pyodide_js import loadedPackages, loadPackage
    from pyodide_js._api import (  # type: ignore[import]
        loadBinaryFile,
        loadDynlibsFromPackage,
    )

    LOCKFILE_PACKAGES = pyodide_js._api.lockfile_packages.to_py()
    LOCKFILE_INFO = pyodide_js._api.lockfile_info.to_py()
except ImportError:
    if IN_BROWSER:
        raise
    # Otherwise, this is pytest test collection so let it go.


class CompatibilityInPyodide(CompatibilityLayer):
    class HttpStatusError(Exception):
        status_code: int
        message: str

        def __init__(self, status_code: int, message: str):
            self.status_code = status_code
            self.message = message
            super().__init__(message)

    @staticmethod
    async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
        parsed_url = urlparse(url)
        if parsed_url.scheme == "emfs":
            return Path(parsed_url.path).read_bytes()
        if parsed_url.scheme == "file":
            return (await loadBinaryFile(parsed_url.path)).to_bytes()

        return await (await pyfetch(url, **kwargs)).bytes()

    @staticmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, str]
    ) -> tuple[str, dict[str, str]]:
        try:
            response = await pyfetch(url, **kwargs)
            response.raise_for_status()
        except HttpStatusError as e:
            raise CompatibilityInPyodide.HttpStatusError(e.status, str(e)) from e

        content = await response.string()
        headers: dict[str, str] = response.headers

        return content, headers

    loadedPackages = loadedPackages

    get_dynlibs = get_dynlibs

    loadDynlibsFromPackage = loadDynlibsFromPackage

    loadPackage = loadPackage

    to_js = to_js

    lockfile_info = LOCKFILE_INFO

    lockfile_packages = LOCKFILE_PACKAGES
