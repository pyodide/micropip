import re
from io import BytesIO
from pathlib import Path
from typing import IO, Any
from zipfile import ZipFile

REPODATA_PACKAGES: dict[str, dict[str, Any]] = {}


class loadedPackages:
    @staticmethod
    def to_py():
        return {}


from urllib.request import Request, urlopen
from urllib.response import addinfourl


def _fetch(url: str, kwargs: dict[str, Any]) -> addinfourl:
    return urlopen(Request(url, **kwargs))


async def fetch_bytes(url: str, kwargs: dict[str, Any]) -> IO[bytes]:
    response = _fetch(url, kwargs=kwargs)
    return BytesIO(response.read())


async def fetch_string_and_headers(
    url: str, kwargs: dict[str, Any]
) -> tuple[str, dict[str, str]]:
    response = _fetch(url, kwargs=kwargs)
    headers = {k.lower(): v for k, v in response.headers.items()}
    return response.read().decode(), headers


async def loadDynlib(dynlib: str, is_shared_lib: bool) -> None:
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


# Vendored from pip
class UnsupportedWheel(Exception):
    """Unsupported wheel."""


def wheel_dist_info_dir(source: ZipFile, name: str) -> str:
    """Returns the name of the contained .dist-info directory.
    Raises UnsupportedWheel if not found, >1 found, or it doesn't match the
    provided name.
    """
    # Zip file path separators must be /
    subdirs = {p.split("/", 1)[0] for p in source.namelist()}

    info_dirs = [s for s in subdirs if s.endswith(".dist-info")]

    if not info_dirs:
        raise UnsupportedWheel(f".dist-info directory not found in wheel {name!r}")

    if len(info_dirs) > 1:
        raise UnsupportedWheel(
            "multiple .dist-info directories found in wheel {!r}: {}".format(
                name, ", ".join(info_dirs)
            )
        )

    info_dir = info_dirs[0]

    info_dir_name = canonicalize_name(info_dir)
    canonical_name = canonicalize_name(name)
    if not info_dir_name.startswith(canonical_name):
        raise UnsupportedWheel(
            ".dist-info directory {!r} does not start with {!r}".format(
                info_dir, canonical_name
            )
        )

    return info_dir


class pyodide_js_:
    def __get__(self, attr):
        raise RuntimeError(f"Attempted to access property '{attr}' on pyodide_js dummy")


REPODATA_INFO: dict[str, str] = {}


def loadPackage(packages: str | list[str]) -> None:
    pass


__all__ = [
    "loadDynlib",
    "fetch_bytes",
    "fetch_string_and_headers",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadPackage",
    "get_dynlibs",
    "wheel_dist_info_dir",
    "to_js",
]
