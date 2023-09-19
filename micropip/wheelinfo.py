import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any
from urllib.parse import ParseResult, urlparse
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.version import Version

from ._compat import (
    fetch_bytes,
    get_dynlibs,
    loadDynlib,
    loadedPackages,
    wheel_dist_info_dir,
)
from ._utils import parse_wheel_filename
from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel
from .externals.pip._vendor.pkg_resources import Distribution


@dataclass
class WheelInfo:
    """
    WheelInfo represents a wheel file and its metadata (e.g. URL and hash)
    """

    name: str
    version: Version
    filename: str
    build: tuple[int, str] | tuple[()]
    tags: frozenset[Tag]
    url: str
    parsed_url: ParseResult
    sha256: str | None = None
    size: int | None = None  # Size in bytes, if available (PEP 700)

    # Fields below are only available after downloading the wheel, i.e. after calling `download()`.

    _data: IO[bytes] | None = None  # Wheel file contents.
    _dist: Distribution | None = None  # pkg_resources.Distribution object.
    _requires: list[Requirement] | None = None  # List of requirements.

    # Note: `_project_name`` is taken from the wheel metadata, while `name` is taken from the wheel filename or metadata of the package index.
    #       They are mostly the same, but can be different in some weird cases (e.g. a user manually renaming the wheel file), so just to be safe we store both.
    _project_name: str | None = None  # Project name.

    # Path to the .dist-info directory. This is only available after extracting the wheel, i.e. after calling `extract()`.
    _dist_info: Path | None = None

    @classmethod
    def from_url(cls, url: str) -> "WheelInfo":
        """Parse wheels URL and extract available metadata

        See https://www.python.org/dev/peps/pep-0427/#file-name-convention
        """
        parsed_url = urlparse(url)
        file_name = Path(parsed_url.path).name
        name, version, build, tags = parse_wheel_filename(file_name)
        return WheelInfo(
            name=name,
            version=version,
            filename=file_name,
            build=build,
            tags=tags,
            url=url,
            parsed_url=parsed_url,
        )

    @classmethod
    def from_package_index(
        cls,
        name: str,
        filename: str,
        url: str,
        version: Version,
        sha256: str | None,
        size: int | None,
    ) -> "WheelInfo":
        """Extract available metadata from response received from package index"""
        parsed_url = urlparse(url)
        _, _, build, tags = parse_wheel_filename(filename)

        return WheelInfo(
            name=name,
            version=version,
            filename=filename,
            build=build,
            tags=tags,
            url=url,
            parsed_url=parsed_url,
            sha256=sha256,
            size=size,
        )

    async def install(self, target: Path) -> None:
        """
        Install the wheel to the target directory.

        The installation process is as follows:
            0. A wheel needs to be downloaded before it can be installed. This is done by calling `download()`.
            1. The wheel is validated by comparing its hash with the one provided by the package index.
            2. The wheel is extracted to the target directory.
            3. The wheel's shared libraries are loaded.
            4. The wheel's metadata is set.
        """
        if not self._data:
            raise RuntimeError(
                "Micropip internal error: attempted to install wheel before downloading it?"
            )
        self._validate()
        self._extract(target)
        await self._load_libraries(target)
        self._set_installer()

    async def download(self, fetch_kwargs: dict[str, Any]):
        if self._data is not None:
            return

        self._data = await self._fetch_bytes(fetch_kwargs)
        with ZipFile(self._data) as zip_file:
            self._dist = pkg_resources_distribution_for_wheel(
                zip_file, self.name, "???"
            )

        self._project_name = self._dist.project_name
        if self._project_name == "UNKNOWN":
            self._project_name = self.name

    def requires(self, extras: set[str]) -> list[str]:
        """
        Get a list of requirements for the wheel.
        """
        if not self._dist:
            raise RuntimeError(
                "Micropip internal error: attempted to access wheel 'requires' before downloading it?"
            )
        requires = self._dist.requires(extras)
        self._requires = requires
        return requires

    async def _fetch_bytes(self, fetch_kwargs: dict[str, Any]):
        try:
            return await fetch_bytes(self.url, fetch_kwargs)
        except OSError as e:
            if self.parsed_url.hostname in [
                "files.pythonhosted.org",
                "cdn.jsdelivr.net",
            ]:
                raise e
            else:
                raise ValueError(
                    f"Can't fetch wheel from '{self.url}'. "
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS). "
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

    def _validate(self):
        if self.sha256 is None:
            # No checksums available, e.g. because installing
            # from a different location than PyPI.
            return

        assert self._data
        sha256_actual = _generate_package_hash(self._data)
        if sha256_actual != self.sha256:
            raise ValueError("Contents don't match hash")

    def _extract(self, target: Path) -> None:
        assert self._data
        with ZipFile(self._data) as zf:
            zf.extractall(target)
            self._dist_info = target / wheel_dist_info_dir(zf, self.name)

    def _set_installer(self) -> None:
        """
        Set the installer metadata in the wheel's .dist-info directory.
        """
        assert self._data
        wheel_source = "pypi" if self.sha256 is not None else self.url

        self._write_dist_info("PYODIDE_SOURCE", wheel_source)
        self._write_dist_info("PYODIDE_URL", self.url)
        self._write_dist_info("PYODIDE_SHA256", _generate_package_hash(self._data))
        self._write_dist_info("INSTALLER", "micropip")
        if self._requires:
            self._write_dist_info(
                "PYODIDE_REQUIRES", json.dumps(sorted(x.name for x in self._requires))
            )

        name = self._project_name or self.name
        setattr(loadedPackages, name, wheel_source)

    def _write_dist_info(self, file: str, content: str) -> None:
        assert self._dist_info
        (self._dist_info / file).write_text(content)

    async def _load_libraries(self, target: Path) -> None:
        """
        Compiles shared libraries (WASM modules) in the wheel and loads them.
        TODO: integrate with pyodide's dynamic library loading mechanism.
        """
        assert self._data
        dynlibs = get_dynlibs(self._data, ".whl", target)
        await asyncio.gather(*map(lambda dynlib: loadDynlib(dynlib, False), dynlibs))


def _generate_package_hash(data: IO[bytes]) -> str:
    """
    Generate a SHA256 hash of the package data.
    """
    sha256_hash = hashlib.sha256()
    data.seek(0)
    while chunk := data.read(4096):
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
