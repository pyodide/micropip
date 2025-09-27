from pathlib import Path
from urllib.parse import urlparse

from pyodide.ffi import to_js
from pyodide.http import pyfetch

from .compatibility_layer import CompatibilityLayer

try:
    import pyodide_js
    from pyodide_js import loadedPackages, loadPackage, lockfileBaseUrl
    from pyodide_js._api import (  # type: ignore[import]
        install,
        loadBinaryFile,
    )

    LOCKFILE_PACKAGES = pyodide_js._api.lockfile_packages.to_py()
    LOCKFILE_INFO = pyodide_js._api.lockfile_info.to_py()
except ImportError as e:
    raise ImportError("Failed to import pyodide modules, please report this issue to Pyodide team.") from e


class CompatibilityInPyodide(CompatibilityLayer):

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

        response = await pyfetch(url, **kwargs)
        response.raise_for_status()

        content = await response.string()
        headers: dict[str, str] = response.headers

        return content, headers

    loadedPackages = loadedPackages

    install = install

    loadPackage = loadPackage

    to_js = to_js

    lockfile_info = LOCKFILE_INFO

    lockfile_packages = LOCKFILE_PACKAGES

    lockfile_base_url = lockfileBaseUrl
