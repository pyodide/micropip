import json
import string
import sys
from collections import defaultdict
from collections.abc import Callable, Generator
from dataclasses import dataclass
from functools import partial
from typing import Any

from packaging.utils import InvalidWheelFilename
from packaging.version import InvalidVersion, Version

from ._compat import fetch_string_and_headers
from ._utils import is_package_compatible, parse_version
from .externals.mousebender.simple import from_project_details_html

DEFAULT_INDEX_URLS = ["https://pypi.org/simple"]
INDEX_URLS = DEFAULT_INDEX_URLS

_formatter = string.Formatter()


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
    def from_json_api(data: str | bytes | dict[str, Any]) -> "ProjectInfo":
        """
        Parse JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        data_dict = json.loads(data) if isinstance(data, str | bytes) else data

        name: str = data_dict.get("info", {}).get("name", "UNKNOWN")
        releases_raw: dict[str, list[Any]] = data_dict["releases"]

        # Filter out non PEP 440 compliant versions
        releases: dict[Version, list[Any]] = {}
        for version_str, fileinfo in releases_raw.items():
            version, ok = _is_valid_pep440_version(version_str)
            if not ok or not version:
                continue

            # Skip empty releases
            if not fileinfo:
                continue

            releases[version] = fileinfo

        return ProjectInfo._compatible_only(name, releases)

    @staticmethod
    def from_simple_json_api(data: str | bytes | dict[str, Any]) -> "ProjectInfo":
        """
        Parse Simple JSON API response

        https://peps.python.org/pep-0691/
        """

        data_dict = json.loads(data) if isinstance(data, str | bytes) else data
        name, releases = ProjectInfo._parse_pep691_response(data_dict)
        return ProjectInfo._compatible_only(name, releases)

    @staticmethod
    def from_simple_html_api(data: str, pkgname: str) -> "ProjectInfo":
        """
        Parse Simple HTML API response

        https://peps.python.org/pep-0503
        """
        project_detail = from_project_details_html(data, pkgname)
        name, releases = ProjectInfo._parse_pep691_response(project_detail)  # type: ignore[arg-type]
        return ProjectInfo._compatible_only(name, releases)

    @staticmethod
    def _parse_pep691_response(
        resp: dict[str, Any]
    ) -> tuple[str, dict[Version, list[Any]]]:
        name = resp["name"]

        # List of versions (PEP 700), this key is not critical to find packages
        # but it is required to ensure that the same class instance is returned
        # from JSON and Simple JSON APIs.
        # Note that Simple HTML API does not have this key.
        versions = resp.get("versions", [])

        # Group files by version
        releases: dict[Version, list[Any]] = defaultdict(list)

        for version_str in versions:
            version, ok = _is_valid_pep440_version(version_str)
            if not ok or not version:
                continue

            releases[version] = []

        for file in resp["files"]:
            filename = file["filename"]

            if not _fast_check_incompatibility(filename):
                # parsing a wheel filename is expensive, so we do a quick check first
                continue

            try:
                version = parse_version(filename)
            except (InvalidVersion, InvalidWheelFilename):
                continue

            releases[version].append(file)

        return name, releases

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


def _is_valid_pep440_version(version_str: str) -> tuple[Version | None, bool]:
    """
    Check if the given string is a valid PEP 440 version.
    Since parsing a version is expensive, we return the parsed version as well,
    so that it can be reused if needed.
    """
    try:
        version = Version(version_str)
        return version, True
    except InvalidVersion:
        return None, False


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


def _contain_placeholder(url: str, placeholder: str = "package_name") -> bool:
    fields = [parsed[1] for parsed in _formatter.parse(url)]

    return placeholder in fields


def _select_parser(content_type: str, pkgname: str) -> Callable[[str], ProjectInfo]:
    """
    Select the function to parse the response based on the content type.
    """
    match content_type:
        case "application/vnd.pypi.simple.v1+json":
            return ProjectInfo.from_simple_json_api
        case "application/json":
            return ProjectInfo.from_json_api
        case "application/vnd.pypi.simple.v1+html" | "text/html":
            return partial(ProjectInfo.from_simple_html_api, pkgname=pkgname)
        case _:
            raise ValueError(f"Unsupported content type: {content_type}")


async def query_package(
    name: str,
    fetch_kwargs: dict[str, Any] | None = None,
    index_urls: list[str] | str | None = None,
) -> ProjectInfo:
    """
    Query for a package from package indexes.

    Parameters
    ----------
    name
        Name of the package to search for.
    fetch_kwargs
        Keyword arguments to pass to the fetch function.
    index_urls
        A list of URLs or a single URL to use as the package index.
        If None, the default index URL is used.

        If a list of URLs is provided, it will be tried in order until
        it finds a package. If no package is found, an error will be raised.
    """
    global INDEX_URLS

    _fetch_kwargs = fetch_kwargs.copy() if fetch_kwargs else {}

    if "headers" not in _fetch_kwargs:
        _fetch_kwargs["headers"] = {}

    # If not specified, prefer Simple JSON API over Simple HTML API or JSON API
    _fetch_kwargs["headers"].setdefault(
        "accept", "application/vnd.pypi.simple.v1+json, */*;q=0.01"
    )

    if index_urls is None:
        index_urls = INDEX_URLS
    elif isinstance(index_urls, str):
        index_urls = [index_urls]

    for url in index_urls:
        if _contain_placeholder(url):
            url = url.format(package_name=name)
        else:
            url = f"{url}/{name}/"

        try:
            metadata, headers = await fetch_string_and_headers(url, _fetch_kwargs)
        except OSError:
            continue

        content_type = headers.get("content-type", "").lower()
        parser = _select_parser(content_type, name)
        return parser(metadata)
    else:
        raise ValueError(
            f"Can't fetch metadata for '{name}'. "
            "Please make sure you have entered a correct package name "
            "and correctly specified index_urls (if you changed them)."
        )
