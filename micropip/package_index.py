import json
import string
import sys
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from ._utils import is_package_compatible, parse_version
from ._vendored.mousebender.simple import from_project_details_html
from ._vendored.packaging.src.packaging.utils import InvalidWheelFilename
from ._vendored.packaging.src.packaging.version import InvalidVersion, Version
from .types import DistributionMetadata
from .wheelinfo import WheelInfo

# Special values that can be used in ``index_urls``.
# "PYPI" is replaced with the PyPI URL.
PYPI = "PYPI"
# "PYODIDE" means "look up the package in the Pyodide lock file at this position".
PYODIDE = "PYODIDE"
PYPI_URL = "https://pypi.org/simple"
DEFAULT_INDEX_URLS = [PYPI_URL]

_formatter = string.Formatter()


@dataclass
class ProjectFile:
    """
    A file of a project on a package index, as in the Simple JSON API (PEP 691).

    Files are not filtered: a :py:class:`ProjectPage` lists every file, whether or
    not it is compatible with the current platform.
    """

    filename: str
    url: str
    """Absolute URL of the file."""
    hashes: dict[str, str] = field(default_factory=dict)
    """Hashes of the file, keyed by algorithm (e.g. ``{"sha256": "..."}``)."""
    core_metadata: DistributionMetadata = None
    """Whether the metadata of the file is available separately (PEP 658 / PEP 714), and its hashes."""
    yanked: bool | str = False
    """Whether the file is yanked (PEP 592), or the reason if one is given."""
    requires_python: str | None = None
    size: int | None = None
    """Size of the file in bytes, if known (PEP 700)."""

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_url: str = "") -> "ProjectFile":
        """
        Create a file from a Simple JSON API (``hashes``) or JSON API (``digests``)
        file entry. A relative ``url`` is resolved against ``base_url``.
        """
        url = data["url"]
        if not urlparse(url).netloc:
            url = urljoin(base_url, url)
        return cls(
            filename=data["filename"],
            url=url,
            hashes=dict(data.get("hashes") or data.get("digests") or {}),
            core_metadata=data.get("core-metadata")
            or data.get("data-dist-info-metadata"),
            yanked=data.get("yanked", False),
            requires_python=data.get("requires-python") or data.get("requires_python"),
            size=data.get("size"),
        )


@dataclass
class ProjectPage:
    """
    All files of a project on a package index, as in the Simple JSON API (PEP 691).

    This is what a :py:class:`micropip.sources.Source` returns. It is not
    filtered by platform compatibility, so resolvers can apply their own rules.
    """

    name: str
    files: list[ProjectFile] = field(default_factory=list)
    versions: list[str] = field(default_factory=list)
    """All versions of the project, including ones without files (PEP 700), if known."""

    @classmethod
    def from_simple_json_api(
        cls, data: str | bytes | dict[str, Any], base_url: str = ""
    ) -> "ProjectPage":
        """
        Parse a Simple JSON API response (PEP 691).

        https://peps.python.org/pep-0691/
        """
        data_dict = json.loads(data) if isinstance(data, str | bytes) else data
        return cls(
            name=data_dict["name"],
            files=[ProjectFile.from_dict(f, base_url) for f in data_dict["files"]],
            versions=list(data_dict.get("versions", [])),
        )

    @classmethod
    def from_simple_html_api(cls, data: str, name: str, base_url: str) -> "ProjectPage":
        """
        Parse a Simple HTML API response (PEP 503).

        https://peps.python.org/pep-0503
        """
        project_detail: dict[str, Any] = from_project_details_html(data, name)  # type: ignore[assignment]
        return cls.from_simple_json_api(project_detail, base_url)

    @classmethod
    def from_json_api(
        cls,
        data: str | bytes | dict[str, Any],
        base_url: str = "",
        name: str | None = None,
    ) -> "ProjectPage":
        """
        Parse a JSON API response (``https://pypi.org/pypi/<name>/json``).

        ``name`` is used if the response has no ``info.name``. A relative file
        ``url`` is resolved against ``base_url``.

        https://warehouse.pypa.io/api-reference/json.html
        """
        data_dict = json.loads(data) if isinstance(data, str | bytes) else data

        project_name: str = data_dict.get("info", {}).get("name") or name or "UNKNOWN"
        files: list[ProjectFile] = []
        versions: list[str] = []
        for version_str, release_files in data_dict["releases"].items():
            # Skip empty releases
            if not release_files:
                continue
            versions.append(version_str)
            files.extend(ProjectFile.from_dict(f, base_url) for f in release_files)

        return cls(name=project_name, files=files, versions=versions)

    @classmethod
    def from_response(
        cls, name: str, url: str, content: str, headers: dict[str, str]
    ) -> "ProjectPage":
        """
        Parse the project page of ``name`` fetched from ``url``.

        The format is selected by the ``content-type`` response header.
        """
        content_type = headers.get("content-type", "").lower()
        main_content_type = content_type.split(";")[0].strip()

        match main_content_type:
            case "application/vnd.pypi.simple.v1+json":
                return cls.from_simple_json_api(content, base_url=url)
            case "application/json":
                return cls.from_json_api(content, base_url=url, name=name)
            case "application/vnd.pypi.simple.v1+html" | "text/html":
                return cls.from_simple_html_api(content, name=name, base_url=url)
            case _:
                raise ValueError(
                    f"Error trying to decode url: {url}: "
                    f"unsupported content type: {content_type}"
                )


@dataclass
class ProjectInfo:
    """
    The releases of a project, with only the wheels that are compatible with the
    current platform. This is what micropip's resolver works with; it is built
    from a :py:class:`ProjectPage`.
    """

    name: str  # Name of the package

    # List of releases available for the package, sorted in ascending order by version.
    # For each version, list of wheels compatible with the current platform are stored.
    # If no such wheel is available, the list is empty.
    releases: dict[Version, Generator[WheelInfo, None, None]]

    @classmethod
    def from_project_page(cls, page: ProjectPage) -> "ProjectInfo":
        """Group the files of ``page`` by version, keeping only compatible wheels."""
        releases: dict[Version, list[ProjectFile]] = defaultdict(list)

        # List of versions (PEP 700), this key is not critical to find packages
        # but it is required to ensure that the same class instance is returned
        # from JSON and Simple JSON APIs.
        for version_str in page.versions:
            version, ok = _is_valid_pep440_version(version_str)
            if ok and version:
                releases[version] = []

        for file in page.files:
            if not _fast_check_incompatibility(file.filename):
                # parsing a wheel filename is expensive, so we do a quick check first
                continue

            try:
                version = parse_version(file.filename)
            except (InvalidVersion, InvalidWheelFilename):
                continue

            releases[version].append(file)

        return cls._compatible_only(page.name, releases)

    @classmethod
    def from_json_api(cls, data: str | bytes | dict[str, Any]) -> "ProjectInfo":
        return cls.from_project_page(ProjectPage.from_json_api(data))

    @classmethod
    def from_simple_json_api(cls, data: str | bytes | dict[str, Any]) -> "ProjectInfo":
        return cls.from_project_page(ProjectPage.from_simple_json_api(data))

    @classmethod
    def from_simple_html_api(
        cls, data: str, pkgname: str, index_base_url: str
    ) -> "ProjectInfo":
        return cls.from_project_page(
            ProjectPage.from_simple_html_api(data, pkgname, index_base_url)
        )

    @classmethod
    def _compatible_wheels(
        cls, files: list[ProjectFile], version: Version, name: str
    ) -> Generator[WheelInfo, None, None]:
        for file in files:
            # Checking compatibility takes a bit of time,
            # so we use a generator to avoid doing it for all files.
            compatible, tag_index = is_package_compatible(file.filename)
            if not compatible:
                continue

            yield WheelInfo.from_package_index(
                name=name,
                filename=file.filename,
                url=file.url,
                version=version,
                sha256=file.hashes.get("sha256"),
                size=file.size,
                core_metadata=file.core_metadata,
                yanked_reason=file.yanked,
                best_tag_index=tag_index,
            )

    @classmethod
    def _compatible_only(
        cls, name: str, releases: dict[Version, list[ProjectFile]]
    ) -> "ProjectInfo":
        """
        Return a generator of wheels compatible with the current platform.
        Checking compatibility takes a bit of time, so we use a generator to avoid doing it if not needed.
        """

        releases_compatible = {
            version: cls._compatible_wheels(files, version, name=name)
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

    if filename.endswith("wasm32.whl") and sys.platform == "emscripten":
        return True

    if sys.platform not in filename and not filename.endswith("-none-any.whl"):
        return False

    return True


def _contain_placeholder(url: str, placeholder: str = "package_name") -> bool:
    fields = [parsed[1] for parsed in _formatter.parse(url)]

    return placeholder in fields


def project_urls(name: str, index_urls: list[str] | str) -> list[str]:
    """
    Return the URLs of the project page of ``name`` on each index in ``index_urls``.

    If an index URL contains the ``{package_name}`` placeholder, it is replaced
    with the package name. Otherwise, the package name is appended to the URL.
    The special value ``"PYODIDE"`` (the Pyodide lock file) is skipped.
    """
    if isinstance(index_urls, str):
        index_urls = [index_urls]

    urls = []
    for url in index_urls:
        if url == PYODIDE:
            continue
        if url == PYPI:
            url = PYPI_URL
        if _contain_placeholder(url):
            url = url.format(package_name=name)
        else:
            url = f"{url}/{name}/"
        urls.append(url)
    return urls
