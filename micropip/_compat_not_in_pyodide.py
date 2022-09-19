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


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> IO[bytes]:
    return BytesIO(urlopen(Request(url, headers=kwargs)).read())


async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
    return (await fetch_bytes(url, kwargs)).read().decode()


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
    "fetch_string",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadPackage",
    "get_dynlibs",
    "wheel_dist_info_dir",
    "to_js",
]
