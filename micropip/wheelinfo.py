import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import ParseResult, urlparse

from ._compat import (
    fetch_bytes,
    get_dynlibs,
    loadDynlibsFromPackage,
    loadedPackages,
)
from ._utils import parse_wheel_filename
from ._vendored.packaging.src.packaging.requirements import Requirement
from ._vendored.packaging.src.packaging.tags import Tag
from ._vendored.packaging.src.packaging.version import Version
from .metadata import Metadata, safe_name, wheel_dist_info_dir
from .types import DistributionMetadata


@dataclass
class PackageData:
    file_name: str
    package_type: Literal["shared_library", "package"]
    shared_library: bool


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
    core_metadata: DistributionMetadata = None  # Wheel's metadata (PEP 658 / PEP-714)
    yanked: bool = False  # Whether the wheel has been yanked (PEP-592)

    # Fields below are only available after downloading the wheel, i.e. after calling `download()`.

    _data: bytes | None = field(default=None, repr=False)  # Wheel file contents.
    _metadata: Metadata | None = None  # Wheel metadata.
    _requires: list[Requirement] | None = None  # List of requirements.

    # Path to the .dist-info directory.
    # This is only available after extracting the wheel, i.e. after calling `extract()`.
    _dist_info: Path | None = None

    def __post_init__(self):
        assert (
            self.url.startwith(p) for p in ("http:", "https:", "emfs:", "file:")
        ), self.url
        self._project_name = safe_name(self.name)
        self.metadata_url = self.url + ".metadata"

    @classmethod
    def from_url(cls, url: str) -> "WheelInfo":
        """Parse wheels URL and extract available metadata

        See https://www.python.org/dev/peps/pep-0427/#file-name-convention
        """
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            parsed_url = ParseResult(
                scheme="file",
                netloc=parsed_url.netloc,
                path=parsed_url.path,
                params=parsed_url.params,
                query=parsed_url.query,
                fragment=parsed_url.fragment,
            )
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
        core_metadata: DistributionMetadata = None,
        yanked: bool = False,
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
            core_metadata=core_metadata,
            yanked=yanked,
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
        _validate_sha256_checksum(self._data, self.sha256)
        self._extract(target)
        await self._load_libraries(target)
        self._set_installer()

    async def download(self, fetch_kwargs: dict[str, Any]):
        if self._data is not None:
            return

        self._data = await self._fetch_bytes(self.url, fetch_kwargs)

        # The wheel's metadata might be downloaded separately from the wheel itself.
        # If it is not downloaded yet or if the metadata is not available, extract it from the wheel.
        if self._metadata is None:
            with zipfile.ZipFile(io.BytesIO(self._data)) as zf:
                metadata_path = (
                    Path(wheel_dist_info_dir(zf, self.name)) / Metadata.PKG_INFO
                )
                self._metadata = Metadata(zipfile.Path(zf, str(metadata_path)))

    def pep658_metadata_available(self) -> bool:
        """
        Check if the wheel's metadata is exposed via PEP 658.
        """
        return self.core_metadata is not None

    async def download_pep658_metadata(
        self,
        fetch_kwargs: dict[str, Any],
    ) -> None:
        """
        Download the wheel's metadata. If the metadata is not available, return None.
        """
        if self.core_metadata is None:
            return None

        data = await self._fetch_bytes(self.metadata_url, fetch_kwargs)

        match self.core_metadata:
            case {"sha256": checksum}:  # sha256 checksum available
                _validate_sha256_checksum(data, checksum)
            case _:  # no checksum available
                pass

        self._metadata = Metadata(data)

    def requires(self, extras: set[str]) -> list[Requirement]:
        """
        Get a list of requirements for the wheel.
        """
        if self._metadata is None:
            raise RuntimeError(
                "Micropip internal error: attempted to get requirements before downloading the wheel?"
            )

        requires = self._metadata.requires(extras)
        self._requires = requires
        return requires

    async def _fetch_bytes(self, url: str, fetch_kwargs: dict[str, Any]):
        if self.parsed_url.scheme not in ("https", "http", "emfs", "file"):
            # Don't raise ValueError it gets swallowed
            raise TypeError(
                f"Cannot download from a non-remote location: {url!r} ({self.parsed_url!r})"
            )
        try:
            bytes = await fetch_bytes(url, fetch_kwargs)
            return bytes
        except OSError as e:
            if self.parsed_url.hostname in [
                "files.pythonhosted.org",
                "cdn.jsdelivr.net",
            ]:
                raise e
            else:
                raise ValueError(
                    f"Can't fetch wheel from {url!r}. "
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS). "
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

    def _extract(self, target: Path) -> None:
        assert self._data
        with zipfile.ZipFile(io.BytesIO(self._data)) as zf:
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

        setattr(loadedPackages, self._project_name, wheel_source)

    def _write_dist_info(self, file: str, content: str) -> None:
        assert self._dist_info
        (self._dist_info / file).write_text(content)

    async def _load_libraries(self, target: Path) -> None:
        """
        Compiles shared libraries (WASM modules) in the wheel and loads them.
        """
        assert self._data

        pkg = PackageData(
            file_name=self.filename,
            package_type="package",
            shared_library=False,
        )

        dynlibs = get_dynlibs(io.BytesIO(self._data), ".whl", target)
        await loadDynlibsFromPackage(pkg, dynlibs)


def _validate_sha256_checksum(data: bytes, expected: str | None = None) -> None:
    if expected is None:
        # No checksums available, e.g. because installing
        # from a different location than PyPI.
        return

    actual = _generate_package_hash(data)
    if actual != expected:
        raise RuntimeError(f"Invalid checksum: expected {expected}, got {actual}")


def _generate_package_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
