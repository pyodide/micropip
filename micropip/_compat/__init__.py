from pathlib import Path
import sys
from typing import IO, TYPE_CHECKING, Any

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from ._compat_in_pyodide import (
        CompatibilityInPyodide as CompatibilityLayer,
    )
else:
    from ._compat_not_in_pyodide import (
        CompatibilityNotInPyodide as CompatibilityLayer,
    )


if TYPE_CHECKING:
    from ..wheelinfo import PackageData

REPODATA_INFO = CompatibilityLayer.repodata_info()
REPODATA_PACKAGES = CompatibilityLayer.repodata_packages()


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
    return CompatibilityLayer.fetch_bytes(url, kwargs)


async def fetch_string_and_headers(
    url: str, kwargs: dict[str, str]
) -> tuple[str, dict[str, str]]:
    return CompatibilityLayer.fetch_string_and_headers(url, kwargs)


loadedPackages = CompatibilityLayer.loadedPackages


async def loadDynlibsFromPackage(pkg_metadata: "PackageData", dynlibs: list[str]):
    return CompatibilityLayer.loadDynlibsFromPackage(pkg_metadata, dynlibs)


async def loadPackage(packages: str | list[str]):
    return CompatibilityLayer.loadPackage(packages)


def get_dynlibs(archive: IO[bytes], suffix: str, target_dir: Path) -> list[str]:
    return CompatibilityLayer.get_dynlibs(archive, suffix, target_dir)


def to_js(
    obj: Any,
    /,
    *,
    depth: int = -1,
    pyproxies=None,
    create_pyproxies: bool = True,
    dict_converter=None,
    default_converter=None,
):
    return CompatibilityLayer.to_js(
        obj,
        depth=depth,
        pyproxies=pyproxies,
        create_pyproxies=create_pyproxies,
        dict_converter=dict_converter,
        default_converter=default_converter,
    )


__all__ = [
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "fetch_bytes",
    "fetch_string_and_headers",
    "loadedPackages",
    "loadDynlibsFromPackage",
    "loadPackage",
    "get_dynlibs",
    "to_js",
]
