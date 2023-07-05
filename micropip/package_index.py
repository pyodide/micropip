from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from packaging.utils import (
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version


@dataclass
class ProjectInfoFile:
    filename: str  # Name of the file
    url: str  # URL to download the file
    version: Version  # Version of the package
    sha256: str  # SHA256 hash of the file

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

    # List of releases available for the package, sorted in ascending order by version
    # Note that a same version may have multiple files (e.g. source distribution, wheel)
    # and this list may contain non-Pyodide compatible files (e.g. binary wheels or source distributions)
    # so it is the responsibility of the caller to filter the list and find the best file
    releases: defaultdict[Version, list[ProjectInfoFile]]

    @staticmethod
    def from_json_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        name: str = data.get("info", {}).get("name", "UNKNOWN")
        _releases: dict[str, Any] = data["releases"]

        releases: defaultdict[Version, list[ProjectInfoFile]] = defaultdict(list)
        for version_str, fileinfo in _releases.items():
            try:
                version = Version(version_str)
            except InvalidVersion:
                # Ignore non PEP 440 compliant versions
                continue

            for file in fileinfo:
                releases[version].append(
                    ProjectInfoFile(
                        filename=file["filename"],
                        url=file["url"],
                        version=version,
                        sha256=file["digests"]["sha256"],
                        size=file["size"],
                    )
                )

        return ProjectInfo(
            name=name,
            releases=releases,
        )

    @staticmethod
    def from_simple_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse Simple API response

        https://peps.python.org/pep-0503/
        https://peps.python.org/pep-0691/
        """

        name = data["name"]
        releases: defaultdict[Version, list[ProjectInfoFile]] = defaultdict(list)
        for file in data["files"]:
            filename = file["filename"]
            try:
                version = _parse_version(filename)
            except InvalidVersion:
                # Ignore non PEP 440 compliant versions
                continue

            releases[version].append(
                ProjectInfoFile(
                    filename=filename,
                    url=file["url"],
                    version=version,
                    # TODO: For now we always expect that the sha256 hash is available.
                    # This is true for PyPI, but may not be true for other package indexes,
                    # since it is not a hard requirement of PEP503.
                    sha256=file["hashes"]["sha256"],
                    size=file["size"] if "size" in file else None,
                )
            )

        return ProjectInfo(
            name=name,
            releases=releases,
        )


def _parse_version(filename: str) -> Version:
    if filename.endswith(".whl"):
        return parse_wheel_filename(filename)[1]
    elif filename.endswith(".tar.gz"):
        return parse_sdist_filename(filename)[1]
    else:
        raise ValueError(f"Unknown file type: {filename}")
