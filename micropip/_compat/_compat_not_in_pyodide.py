import re
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any
from urllib.request import Request, urlopen
from urllib.response import addinfourl

from .compatibility_layer import CompatibilityLayer

if TYPE_CHECKING:
    from ..wheelinfo import PackageData


class CompatibilityNotInPyodide(CompatibilityLayer):

    # Vendored from packaging
    _canonicalize_regex = re.compile(r"[-_.]+")

    class loadedPackages(CompatibilityLayer.loadedPackages):
        @staticmethod
        def to_py():
            return {}

    @staticmethod
    def repodata_info() -> dict[str, str]:
        return {}

    @staticmethod
    def repodata_packages() -> dict[str, dict[str, Any]]:
        return {}

    @staticmethod
    def _fetch(url: str, kwargs: dict[str, Any]) -> addinfourl:
        return urlopen(Request(url, **kwargs))

    @staticmethod
    async def fetch_bytes(url: str, kwargs: dict[str, Any]) -> bytes:
        return CompatibilityNotInPyodide._fetch(url, kwargs=kwargs).read()

    @staticmethod
    async def fetch_string_and_headers(
        url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        response = CompatibilityNotInPyodide._fetch(url, kwargs=kwargs)
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.read().decode(), headers

    @staticmethod
    def get_dynlibs(archive: IO[bytes], suffix: str, target_dir: Path) -> list[str]:
        return []

    @staticmethod
    async def loadDynlibsFromPackage(
        pkg_metadata: "PackageData", dynlibs: list[str]
    ) -> None:
        pass

    @staticmethod
    async def loadPackage(names: str | list[str]) -> None:
        pass

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
