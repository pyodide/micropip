from typing import Any

from .compatibility_layer import CompatibilityLayer

_NOT_SUPPORTED = "micropip can only {} in Pyodide."


class CompatibilityNotInPyodide(CompatibilityLayer):
    """
    Placeholder compatibility layer used when micropip is imported outside of Pyodide.

    It lets ``import micropip`` succeed (e.g. for building docs or running unit tests
    on the host), but anything that needs the Pyodide runtime raises an error.
    Tests that need a working layer on the host should inject their own,
    see ``tests/host_compat.py``.
    """

    class loadedPackages(CompatibilityLayer.loadedPackages):
        @staticmethod
        def to_py():
            return {}

    @staticmethod
    async def fetch_bytes(url: str, kwargs: dict[str, Any]) -> bytes:
        raise RuntimeError(_NOT_SUPPORTED.format("fetch files"))

    @staticmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        raise RuntimeError(_NOT_SUPPORTED.format("fetch files"))

    @staticmethod
    async def install(
        buffer: Any,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        raise RuntimeError(_NOT_SUPPORTED.format("install packages"))

    @staticmethod
    async def loadPackage(names: str | list[str]) -> None:
        raise RuntimeError(_NOT_SUPPORTED.format("load packages"))

    @staticmethod
    def to_js(
        obj: Any,
        /,
        *,
        depth: int = -1,
        pyproxies=None,
        create_pyproxies: bool = True,
        dict_converter=None,
        default_converter=None,
    ) -> Any:
        return obj

    lockfile_info = {}

    lockfile_packages = {}

    lockfile_base_url = None
