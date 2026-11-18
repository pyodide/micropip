"""
A compatibility layer for running micropip's unit tests on the host (outside Pyodide).

micropip only ships a compatibility layer for Pyodide. This one lets host unit
tests fetch files with urllib (e.g. from ``wheel_catalog`` or the mock package
indexes) by injecting it into ``PackageManager``, ``Transaction``,
``query_package``, etc. Installing packages is not supported: tests that install
packages should run in Pyodide.
"""

from typing import Any
from urllib.request import Request, urlopen
from urllib.response import addinfourl

from micropip._compat import CompatibilityLayer


class HostCompatibilityLayer(CompatibilityLayer):
    class loadedPackages(CompatibilityLayer.loadedPackages):
        @staticmethod
        def to_py():
            return {}

    lockfile_info: dict[str, str] = {}

    lockfile_packages: dict[str, dict[str, Any]] = {}

    lockfile_base_url = None

    @staticmethod
    def _fetch(url: str, kwargs: dict[str, Any]) -> addinfourl:
        return urlopen(Request(url, **kwargs))

    @staticmethod
    async def fetch_bytes(url: str, kwargs: dict[str, Any]) -> bytes:
        return HostCompatibilityLayer._fetch(url, kwargs=kwargs).read()

    @staticmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        response = HostCompatibilityLayer._fetch(url, kwargs=kwargs)
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.read().decode(), headers

    @staticmethod
    async def install(
        buffer: Any,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        raise NotImplementedError("Installing packages is only tested in Pyodide.")

    @staticmethod
    async def loadPackage(names: str | list[str]) -> None:
        raise NotImplementedError("Loading packages is only tested in Pyodide.")

    @staticmethod
    def to_js(
        obj: Any,
        /,
        *,
        depth: int = -1,
        pyproxies: Any = None,
        create_pyproxies: bool = True,
        dict_converter: Any = None,
        default_converter: Any = None,
    ) -> Any:
        return obj
