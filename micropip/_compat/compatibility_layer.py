from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..wheelinfo import PackageData


class CompatibilityLayer(ABC):
    """
    CompatibilityLayer represents the interface that must be implemented for each viable environment.

    All of the following methods / properties must be implemented for use both inside and outside of pyodide.
    """

    @property
    @abstractmethod
    def REPODATA_INFO(self) -> dict[str, dict[str, str]]:
        pass

    @property
    @abstractmethod
    def REPODATA_PACKAGES(self) -> dict[str, dict[str, Any]]:
        pass

    @abstractmethod
    async def fetch_bytes(self, url: str) -> bytes:
        pass

    @abstractmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        pass

    @abstractmethod
    def get_dynlibs(archive: IO[bytes], suffix: str, target_dir: Path) -> list[str]:
        pass

    @abstractmethod
    async def loadDynlibsFromPackage(
        pkg_metadata: "PackageData", dynlibs: list[str]
    ) -> None:
        pass

    class loadedPackages:
        @staticmethod
        def to_py():
            pass

    @abstractmethod
    async def loadPackage(self, name: str) -> None:
        pass

    @abstractmethod
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
        pass
