"""
A compatibility layer for running micropip's unit tests on the host (outside Pyodide).

micropip only ships a compatibility layer for Pyodide. This one lets host unit
tests fetch files with urllib (e.g. from ``wheel_catalog`` or the mock package
indexes) by injecting an instance into ``PackageManager`` or ``Resolver``.
Installing packages is not supported: tests that install packages should run
in Pyodide.
"""

from urllib.request import Request, urlopen

from micropip._compat import (
    CompatibilityLayer,
    FetchOptions,
    FetchResponse,
    LockedPackage,
    LockFile,
)


class DictLockFile(LockFile):
    """A lock file for host tests, backed by a dict of ``LockedPackage``."""

    def __init__(self, packages: dict[str, LockedPackage]) -> None:
        self.packages = packages

    def get(self, name: str) -> LockedPackage | None:
        return self.packages.get(name)

    async def load(self, names: list[str]) -> list[str]:
        raise NotImplementedError("Loading packages is only tested in Pyodide.")

    def freeze(self) -> str:
        raise NotImplementedError("Freezing is only tested in Pyodide.")


class HostCompatibilityLayer(CompatibilityLayer):
    def __init__(self) -> None:
        self._loaded_packages: dict[str, str] = {}

    async def fetch(self, url: str, options: FetchOptions) -> FetchResponse:
        # Only headers apply to urllib; credentials and extra are browser
        # fetch() options.
        with urlopen(Request(url, headers=options.headers)) as response:
            return FetchResponse(
                response.read(),
                {k.lower(): v for k, v in response.headers.items()},
                response.status,
            )

    async def install(
        self,
        data: bytes,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        raise NotImplementedError("Installing packages is only tested in Pyodide.")

    def loaded_packages(self) -> dict[str, str]:
        return dict(self._loaded_packages)

    def add_loaded_package(self, name: str, source: str) -> None:
        self._loaded_packages[name] = source

    def remove_loaded_package(self, name: str) -> bool:
        return self._loaded_packages.pop(name, None) is not None
