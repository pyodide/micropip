from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from packaging.version import InvalidVersion, Version

from ._utils import is_package_compatible, parse_version


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

    # List of releases available for the package, sorted in ascending order by version.
    # For each version, list of wheels compatible with the current platform are stored.
    # If no such wheel is available, the list is empty.
    releases: dict[Version, list[ProjectInfoFile]]

    @staticmethod
    def from_json_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        name: str = data.get("info", {}).get("name", "UNKNOWN")
        _releases: dict[str, Any] = data["releases"]

        releases: dict[Version, list[ProjectInfoFile]] = defaultdict(list)
        for version_str, fileinfo in _releases.items():
            try:
                version = Version(version_str)
                if str(version) != version_str:
                    # Ignore non PEP 440 compliant versions
                    continue

            except InvalidVersion:
                # Ignore non PEP 440 compliant versions
                continue

            for file in fileinfo:
                filename = file["filename"]

                compatible = is_package_compatible(filename)
                if not compatible:
                    continue

                releases[version].append(
                    ProjectInfoFile(
                        filename=filename,
                        url=file["url"],
                        version=version,
                        sha256=file["digests"]["sha256"],
                        size=file["size"] if "size" in file else None,
                    )
                )

        # Unfortunately, the JSON API seems to compare versions as strings...
        # For example, pytest 3.10.0 is considered newer than 3.2.0.
        # So we need to sort the releases by version again here.
        releases = dict(sorted(releases.items()))

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

            compatible = is_package_compatible(filename)
            if not compatible:
                continue

            try:
                version = parse_version(filename)
            except InvalidVersion:
                # Ignore non PEP 440 compliant versions
                # This should be filtered out by the is_package_compatible check above,
                # but just in case...
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
