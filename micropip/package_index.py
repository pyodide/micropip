import sys
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from packaging.utils import InvalidWheelFilename
from packaging.version import InvalidVersion, Version

from ._utils import is_package_compatible, parse_version


# TODO: Merge this class with WheelInfo
@dataclass
class ProjectInfoFile:
    filename: str  # Name of the file
    url: str  # URL to download the file
    version: Version  # Version of the package
    sha256: str | None  # SHA256 hash of the file

    # Size of the file in bytes, if available (PEP 700)
    # This key is not available in the Simple API HTML response, so this field may be None
    size: int | None = None


@dataclass
class ProjectInfo:
    """
    This class stores common metadata that can be obtained from different APIs (JSON, Simple)
    provided by PyPI. Responses received from PyPI or other package indexes that support the
    same APIs must be converted to this class before being processed by micropip.
    """

    name: str  # Name of the package

    # List of releases available for the package, sorted in ascending order by version.
    # For each version, list of wheels compatible with the current platform are stored.
    # If no such wheel is available, the list is empty.
    releases: dict[Version, Generator[ProjectInfoFile, None, None]]

    @staticmethod
    def from_json_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        name: str = data.get("info", {}).get("name", "UNKNOWN")
        releases_raw: dict[str, list[Any]] = data["releases"]

        # Filter out non PEP 440 compliant versions
        releases: dict[Version, list[Any]] = {}
        for version_str, fileinfo in releases_raw.items():
            try:
                version = Version(version_str)
                if str(version) != version_str:
                    continue

            except InvalidVersion:
                continue

            # Skip empty releases
            if not fileinfo:
                continue

            releases[version] = fileinfo

        return ProjectInfo._compatible_only(name, releases)

    @staticmethod
    def from_simple_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse Simple API response

        https://peps.python.org/pep-0503/
        https://peps.python.org/pep-0691/
        """
        name = data["name"]

        # List of versions (PEP 700), this key is not critical to find packages
        # but it is required to ensure that the same class instance is returned
        # from JSON and Simple APIs.
        versions = data.get("versions", [])

        # Group files by version
        releases: dict[Version, list[Any]] = defaultdict(list)

        for version in versions:
            if not _is_valid_pep440_version(version):
                continue

            releases[Version(version)] = []

        for file in data["files"]:
            filename = file["filename"]

            if not _fast_check_incompatibility(filename):
                # parsing a wheel filename is expensive, so we do a quick check first
                continue

            try:
                version = parse_version(filename)
            except (InvalidVersion, InvalidWheelFilename):
                continue

            releases[version].append(file)

        return ProjectInfo._compatible_only(name, releases)

    @classmethod
    def _compatible_only(
        cls, name: str, releases: dict[Version, list[dict[str, Any]]]
    ) -> "ProjectInfo":
        """
        Return a generator of wheels compatible with the current platform.
        Checking compatibility takes a bit of time, so we use a generator to avoid doing it if not needed.
        """

        def _compatible_wheels(
            files: list[dict[str, Any]], version: Version
        ) -> Generator[ProjectInfoFile, None, None]:
            for file in files:
                filename = file["filename"]

                # Checking compatibility takes a bit of time,
                # so we use a generator to avoid doing it for all files.
                compatible = is_package_compatible(filename)
                if not compatible:
                    continue

                # JSON API has a "digests" key, while Simple API has a "hashes" key.
                hashes = file["digests"] if "digests" in file else file["hashes"]
                sha256 = hashes.get("sha256")

                yield ProjectInfoFile(
                    filename=filename,
                    url=file["url"],
                    version=version,
                    sha256=sha256,
                    size=file.get("size"),
                )

        releases_compatible = {
            version: _compatible_wheels(files, version)
            for version, files in releases.items()
        }

        # Unfortunately, the JSON API seems to compare versions as strings...
        # For example, pytest 3.10.0 is considered newer than 3.2.0.
        # So we need to sort the releases by version again here.
        releases_compatible = dict(sorted(releases_compatible.items()))

        return cls(
            name=name,
            releases=releases_compatible,
        )


def _is_valid_pep440_version(version_str: str) -> bool:
    try:
        version = Version(version_str)
        if str(version) != version_str:
            return False

        return True
    except InvalidVersion:
        return False


def _fast_check_incompatibility(filename: str) -> bool:
    """
    This function returns True is the package is incompatible with the current platform.
    It can be used to quickly filter out incompatible packages before running heavy checks.

    Note that this function may return False for some packages that are actually incompatible.
    So it should only be used as a quick check.
    """
    if not filename.endswith(".whl"):
        return False

    if sys.platform not in filename and not filename.endswith("-none-any.whl"):
        return False

    return True
