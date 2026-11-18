"""
A compatibility layer for running micropip's unit tests on the host (outside Pyodide).

micropip only ships a compatibility layer for Pyodide. This one lets host unit
tests fetch files with urllib (e.g. from ``wheel_catalog`` or the mock package
indexes) by injecting an instance into ``PackageManager`` or ``Resolver``.
Installing packages is not supported: tests that install packages should run
in Pyodide.
"""

from typing import Any
from urllib.request import Request, urlopen
from urllib.response import addinfourl

from micropip._compat import CompatibilityLayer


class HostCompatibilityLayer(CompatibilityLayer):
    def __init__(self) -> None:
        self.lockfile_info: dict[str, str] = {}
        self.lockfile_packages: dict[str, dict[str, Any]] = {}
        self.lockfile_base_url = None
        self._loaded_packages: dict[str, str] = {}

    @staticmethod
    def _fetch(url: str, kwargs: dict[str, Any]) -> addinfourl:
        return urlopen(Request(url, **kwargs))

    async def fetch_bytes(self, url: str, kwargs: dict[str, Any]) -> bytes:
        return self._fetch(url, kwargs=kwargs).read()

    async def fetch_string_and_headers(
        self, url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        response = self._fetch(url, kwargs=kwargs)
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.read().decode(), headers

    async def install(
        self,
        data: bytes,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        raise NotImplementedError("Installing packages is only tested in Pyodide.")

    async def load_packages(self, names: list[str]) -> None:
        raise NotImplementedError("Loading packages is only tested in Pyodide.")

    def loaded_packages(self) -> dict[str, str]:
        return dict(self._loaded_packages)

    def add_loaded_package(self, name: str, source: str) -> None:
        self._loaded_packages[name] = source

    def remove_loaded_package(self, name: str) -> bool:
        return self._loaded_packages.pop(name, None) is not None
