import importlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.response import addinfourl

from .compatibility_layer import CompatibilityLayer


class CompatibilityNotInPyodide(CompatibilityLayer):

    # Vendored from packaging
    # TODO: use packaging APIs here instead?
    _canonicalize_regex = re.compile(r"[-_.]+")

    class loadedPackages(CompatibilityLayer.loadedPackages):
        @staticmethod
        def to_py():
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
    async def install(
        buffer: Any,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """
        Install a package from a buffer to the specified directory.
        TODO: Remove host tests that depends on internal behavior of install (https://github.com/pyodide/micropip/issues/210)
              to make the compat code simpler
        """
        from micropip.metadata import wheel_dist_info_dir

        with zipfile.ZipFile(io.BytesIO(buffer)) as zf:
            zf.extractall(install_dir)
            pkgname = filename.split("-")[0]  # the name will be canonicalized inside wheel_dist_info_dir, so don't care about case
            dist_dir = Path(install_dir) / wheel_dist_info_dir(zf, pkgname)

        if metadata:
            for k, v in metadata.items():
                (dist_dir / k).write_text(v)

        importlib.invalidate_caches()

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

    lockfile_info = {}

    lockfile_packages = {}
