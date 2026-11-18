from pathlib import Path
from typing import Any
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
except ImportError as e:
    raise ImportError(
        "Failed to import pyodide modules, please report this issue to Pyodide team."
    ) from e


class PyodideCompatibilityLayer(CompatibilityLayer):
    """
    The default compatibility layer, used in the Pyodide runtime.

    Subclass it to change part of the default behavior, e.g. ``fetch_bytes``.
    """

    def __init__(self) -> None:
        self.lockfile_info = pyodide_js._api.lockfile_info.to_py()
        self.lockfile_packages = pyodide_js._api.lockfile_packages.to_py()
        self.lockfile_base_url = lockfileBaseUrl

    async def fetch_bytes(self, url: str, kwargs: dict[str, Any]) -> bytes:
        parsed_url = urlparse(url)
        if parsed_url.scheme == "emfs":
            return Path(parsed_url.path).read_bytes()
        if parsed_url.scheme == "file":
            return (await loadBinaryFile(parsed_url.path)).to_bytes()

        response = await pyfetch(url, **kwargs)
        response.raise_for_status()
        return await response.bytes()

    async def fetch_string_and_headers(
        self, url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        response = await pyfetch(url, **kwargs)
        response.raise_for_status()

        content = await response.string()
        headers: dict[str, str] = response.headers

        return content, headers

    async def install(
        self,
        data: bytes,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        await install(to_js(data), filename, install_dir, metadata)

    async def load_packages(self, names: list[str]) -> None:
        await loadPackage(to_js(names))

    # pyodide.loadedPackages is shared with the JS side (pyodide.loadPackage
    # consults it), so the Pyodide layer keeps it in sync instead of holding
    # its own state.
    def loaded_packages(self) -> dict[str, str]:
        return loadedPackages.to_py()

    def add_loaded_package(self, name: str, source: str) -> None:
        setattr(loadedPackages, name, source)

    def remove_loaded_package(self, name: str) -> bool:
        if not hasattr(loadedPackages, name):
            return False
        delattr(loadedPackages, name)
        return True
