"""
A compatibility layer for running micropip's unit tests on the host (outside Pyodide).

It fetches files with urllib, so host tests can talk to local HTTP servers
(e.g. ``wheel_catalog`` or the mock package indexes). Installing packages is
not supported: tests that install packages should run in Pyodide.
"""

from typing import Any
from urllib.request import Request, urlopen
from urllib.response import addinfourl

from micropip._compat._compat_not_in_pyodide import CompatibilityNotInPyodide


class HostCompatibilityLayer(CompatibilityNotInPyodide):
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
