import re
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .wheelinfo import PackageData

REPODATA_PACKAGES: dict[str, dict[str, Any]] = {}


class loadedPackages:
    @staticmethod
    def to_py():
        return {}


from urllib.request import Request, urlopen
from urllib.response import addinfourl


def _fetch(url: str, kwargs: dict[str, Any]) -> addinfourl:
    return urlopen(Request(url, **kwargs))


async def fetch_bytes(url: str, kwargs: dict[str, Any]) -> bytes:
    return _fetch(url, kwargs=kwargs).read()


async def fetch_string_and_headers(
    url: str, kwargs: dict[str, Any]
) -> tuple[str, dict[str, str]]:
    response = _fetch(url, kwargs=kwargs)
    headers = {k.lower(): v for k, v in response.headers.items()}
    return response.read().decode(), headers


async def loadDynlibsFromPackage(
    pkg_metadata: "PackageData", dynlibs: list[str]
) -> None:
    pass


def get_dynlibs(archive: IO[bytes], suffix: str, target_dir: Path) -> list[str]:
    return []


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


# Vendored from packaging
_canonicalize_regex = re.compile(r"[-_.]+")


def canonicalize_name(name: str) -> str:
    # This is taken from PEP 503.
    return _canonicalize_regex.sub("-", name).lower()


class pyodide_js_:
    def __get__(self, attr):
        raise RuntimeError(f"Attempted to access property '{attr}' on pyodide_js dummy")


REPODATA_INFO: dict[str, str] = {}


def loadPackage(packages: str | list[str]) -> None:
    pass


__all__ = [
    "loadDynlibsFromPackage",
    "fetch_bytes",
    "fetch_string_and_headers",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadPackage",
    "get_dynlibs",
    "to_js",
]
