from dataclasses import dataclass
from typing import Any

from packaging.utils import (
    parse_wheel_filename,
    parse_sdist_filename,
)


@dataclass
class ProjectInfoFiles:
    filename: str  # Name of the file
    url: str  # URL to download the file
    version: str  # Version of the package
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

    # List of versions available, if available (PEP 700)
    # This key is not available in the Simple API HTML response, so this field may be None
    versions: list[str] | None

    # List of files available for the package, sorted in ascending order by version
    # Note that a same version may have multiple files (e.g. source distribution, wheel)
    # and this list may contain non-Pyodide compatible files (e.g. binary wheels or source distributions)
    # so it is the responsibility of the caller to filter the list and find the best file
    files: list[ProjectInfoFiles]

    @staticmethod
    def from_json_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        name = data["info"]["name"]
        releases = data["releases"]
        versions = list(releases.keys())

        files = []
        for version, fileinfo in releases.items():
            for file in fileinfo:
                files.append(
                    ProjectInfoFiles(
                        filename=file["filename"],
                        url=file["url"],
                        version=version,
                        sha256=file["digests"]["sha256"],
                        size=file["size"],
                    )
                )

        return ProjectInfo(
            name=name,
            versions=versions,
            files=files,
        )

    @staticmethod
    def from_simple_api(data: dict[str, Any]) -> "ProjectInfo":
        """
        Parse Simple API response

        https://peps.python.org/pep-0503/
        https://peps.python.org/pep-0691/
        """

        name = data["name"]
        versions = data["versions"] if "versions" in data else None
        files = []
        for file in data["files"]:
            filename = file["filename"]
            version = _parse_version(filename)[1]

            files.append(
                ProjectInfoFiles(
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
            versions=versions,
            files=files,
        )


def _parse_version(filename: str):
    if filename.endswith(".whl"):
        return str(parse_wheel_filename(filename)[1])
    elif filename.endswith(".tar.gz"):
        return str(parse_sdist_filename(filename)[1])
