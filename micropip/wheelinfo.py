import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import ParseResult, unquote, urlparse

from ._compat import CompatibilityLayer
from ._utils import best_compatible_tag_index, parse_wheel_filename
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
    yanked_reason: str | bool = (
        False  # Whether the wheel has been yanked and the reason (if given) (PEP-592)
    )
    _best_tag_index: int | None = field(default=None, repr=False, compare=False)

    # Fields below are only available after downloading the wheel, i.e. after calling `set_data()`.

    _data: bytes | None = field(default=None, repr=False)  # Wheel file contents.
    _metadata: Metadata | None = None  # Wheel metadata.
    _requires: list[Requirement] | None = None  # List of requirements.

    def __post_init__(self):
        assert (
            self.url.startwith(p) for p in ("http:", "https:", "emfs:", "file:")
        ), self.url
        self._project_name = safe_name(self.name)
        self.metadata_url = self.url + ".metadata"
        self.yanked = bool(self.yanked_reason)

    @property
    def best_tag_index(self) -> int | None:
        """
        Returns an index if a compatible tag exists, otherwise None.
        """
        if self._best_tag_index is None:
            self._best_tag_index = best_compatible_tag_index(self.tags)
        return self._best_tag_index

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
        file_name = Path(unquote(parsed_url.path)).name
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
        yanked_reason: str | bool = False,
        best_tag_index: int | None = None,
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
            yanked_reason=yanked_reason,
            _best_tag_index=best_tag_index,
        )

    async def install(self, target: Path, compat_layer: CompatibilityLayer) -> None:
        """
        Install the wheel to the target directory.

        The installation process is as follows:
            0. A wheel needs to be downloaded before it can be installed (see `set_data()`).
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
        await self._install(target, compat_layer)

    @property
    def downloaded(self) -> bool:
        """Whether the wheel file has been downloaded (see :meth:`set_data`)."""
        return self._data is not None

    def set_data(self, data: bytes) -> None:
        """
        Set the contents of the downloaded wheel file.

        If the wheel's metadata is not set yet (see :meth:`set_pep658_metadata`),
        it is extracted from the wheel.
        """
        self._data = data

        if self._metadata is None:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                metadata_path = (
                    Path(wheel_dist_info_dir(zf, self.name)) / Metadata.PKG_INFO
                )
                self._metadata = Metadata(zipfile.Path(zf, str(metadata_path)))

    def pep658_metadata_available(self) -> bool:
        """
        Check if the wheel's metadata is exposed via PEP 658.
        """
        return self.core_metadata is not None

    def set_pep658_metadata(self, data: bytes) -> None:
        """
        Set the wheel's metadata, downloaded separately from the wheel (PEP 658).

        Raises ``RuntimeError`` if the index provided a checksum that does not match.
        """
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

    async def _install(self, target: Path, compat_layer: CompatibilityLayer) -> None:
        """
        Install the wheel to the target directory.
        """
        assert self._data

        wheel_source = "pypi" if self.sha256 is not None else self.url
        metadata = {
            "PYODIDE_SOURCE": wheel_source,
            "PYODIDE_URL": self.url,
            "PYODIDE_SHA256": _generate_package_hash(self._data),
            "INSTALLER": "micropip",
        }

        if self._requires:
            metadata["PYODIDE_REQUIRES"] = json.dumps(
                sorted(x.name for x in self._requires)
            )

        await compat_layer.install(
            self._data,
            self.filename,
            str(target),
            metadata,
        )

        compat_layer.add_loaded_package(self._project_name, wheel_source)


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
