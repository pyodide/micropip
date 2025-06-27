from abc import ABC, abstractmethod
from typing import Any


class CompatibilityLayer(ABC):
    """
    CompatibilityLayer represents the interface that must be implemented for each viable environment.

    All of the following methods / properties must be implemented for use both inside and outside of pyodide.
    """

    class loadedPackages(ABC):
        @staticmethod
        @abstractmethod
        def to_py():
            pass

    lockfile_info: dict[str, str]

    lockfile_packages: dict[str, dict[str, Any]]

    @staticmethod
    @abstractmethod
    async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        pass

    @staticmethod
    @abstractmethod
    async def install(
        buffer: Any,  # JsBuffer
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        pass

    @staticmethod
    @abstractmethod
    async def loadPackage(names: str | list[str]) -> None:
        pass

    @staticmethod
    @abstractmethod
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
        pass
