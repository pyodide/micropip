# Adapted from: https://github.com/brettcannon/mousebender/blob/main/mousebender/simple.py
# Only relevant parts are included here.

import html
import html.parser
import urllib.parse
import warnings
from typing import Any, Dict, List, Optional, Union, Literal, TypeAlias, TypedDict

import packaging.utils


ACCEPT_JSON_V1 = "application/vnd.pypi.simple.v1+json"



class UnsupportedAPIVersion(Exception):
    """The major version of an API response is not supported."""

    def __init__(self, version: str) -> None:
        """Initialize the exception with a message based on the provided version."""
        super().__init__(f"Unsupported API major version: {version!r}")


class APIVersionWarning(Warning):
    """The minor version of an API response is not supported."""

    def __init__(self, version: str) -> None:
        """Initialize the warning with a message based on the provided version."""
        super().__init__(f"Unsupported API minor version: {version!r}")


class UnsupportedMIMEType(Exception):
    """An unsupported MIME type was provided in a ``Content-Type`` header."""


_Meta_1_0 = TypedDict("_Meta_1_0", {"api-version": Literal["1.0"]})
_Meta_1_1 = TypedDict("_Meta_1_1", {"api-version": Literal["1.1"]})


_HashesDict: TypeAlias = Dict[str, str]

_OptionalProjectFileDetails_1_0 = TypedDict(
    "_OptionalProjectFileDetails_1_0",
    {
        "requires-python": str,
        "dist-info-metadata": Union[bool, _HashesDict],
        "gpg-sig": bool,
        "yanked": Union[bool, str],
    },
    total=False,
)


class ProjectFileDetails_1_0(_OptionalProjectFileDetails_1_0):
    """A :class:`~typing.TypedDict` for the ``files`` key of :class:`ProjectDetails_1_0`."""

    filename: str
    url: str
    hashes: _HashesDict


_OptionalProjectFileDetails_1_1 = TypedDict(
    "_OptionalProjectFileDetails_1_1",
    {
        "requires-python": str,
        "dist-info-metadata": Union[bool, _HashesDict],
        "gpg-sig": bool,
        "yanked": Union[bool, str],
        # PEP 700
        "upload-time": str,
    },
    total=False,
)


class ProjectFileDetails_1_1(_OptionalProjectFileDetails_1_1):
    """A :class:`~typing.TypedDict` for the ``files`` key of :class:`ProjectDetails_1_1`."""

    filename: str
    url: str
    hashes: _HashesDict
    # PEP 700
    size: int


class ProjectDetails_1_0(TypedDict):
    """A :class:`~typing.TypedDict` for a project details response (:pep:`691`)."""

    meta: _Meta_1_0
    name: packaging.utils.NormalizedName
    files: list[ProjectFileDetails_1_0]


class ProjectDetails_1_1(TypedDict):
    """A :class:`~typing.TypedDict` for a project details response (:pep:`700`)."""

    meta: _Meta_1_1
    name: packaging.utils.NormalizedName
    files: list[ProjectFileDetails_1_1]
    # PEP 700
    versions: List[str]


ProjectDetails: TypeAlias = Union[ProjectDetails_1_0, ProjectDetails_1_1]


def _check_version(tag: str, attrs: Dict[str, Optional[str]]) -> None:
    if (
        tag == "meta"
        and attrs.get("name") == "pypi:repository-version"
        and "content" in attrs
        and attrs["content"]
    ):
        version = attrs["content"]
        major_version, minor_version = map(int, version.split("."))
        if major_version != 1:
            raise UnsupportedAPIVersion(version)
        elif minor_version > 1:
            warnings.warn(APIVersionWarning(version), stacklevel=7)


class _ArchiveLinkHTMLParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        self.archive_links: List[Dict[str, Any]] = []
        super().__init__()

    def handle_starttag(
        self, tag: str, attrs_list: list[tuple[str, Optional[str]]]
    ) -> None:
        attrs = dict(attrs_list)
        _check_version(tag, attrs)
        if tag != "a":
            return
        # PEP 503:
        # The href attribute MUST be a URL that links to the location of the
        # file for download ...
        if "href" not in attrs or not attrs["href"]:
            return
        full_url: str = attrs["href"]
        parsed_url = urllib.parse.urlparse(full_url)
        # PEP 503:
        # ... the text of the anchor tag MUST match the final path component
        # (the filename) of the URL.
        _, _, raw_filename = parsed_url.path.rpartition("/")
        filename = urllib.parse.unquote(raw_filename)
        url = urllib.parse.urlunparse((*parsed_url[:5], ""))
        args: Dict[str, Any] = {"filename": filename, "url": url}
        # PEP 503:
        # The URL SHOULD include a hash in the form of a URL fragment with the
        # following syntax: #<hashname>=<hashvalue> ...
        if parsed_url.fragment:
            hash_algo, hash_value = parsed_url.fragment.split("=", 1)
            args["hashes"] = hash_algo.lower(), hash_value
        # PEP 503:
        # A repository MAY include a data-requires-python attribute on a file
        # link. This exposes the Requires-Python metadata field ...
        # In the attribute value, < and > have to be HTML encoded as &lt; and
        # &gt;, respectively.
        if "data-requires-python" in attrs and attrs["data-requires-python"]:
            requires_python_data = html.unescape(attrs["data-requires-python"])
            args["requires-python"] = requires_python_data
        # PEP 503:
        # A repository MAY include a data-gpg-sig attribute on a file link with
        # a value of either true or false ...
        if "data-gpg-sig" in attrs:
            args["gpg-sig"] = attrs["data-gpg-sig"] == "true"
        # PEP 592:
        # Links in the simple repository MAY have a data-yanked attribute which
        # may have no value, or may have an arbitrary string as a value.
        if "data-yanked" in attrs:
            args["yanked"] = attrs.get("data-yanked") or True
        # PEP 658:
        # ... each anchor tag pointing to a distribution MAY have a
        # data-dist-info-metadata attribute.
        if "data-dist-info-metadata" in attrs:
            found_metadata = attrs.get("data-dist-info-metadata")
            if found_metadata and found_metadata != "true":
                # The repository SHOULD provide the hash of the Core Metadata
                # file as the data-dist-info-metadata attribute's value using
                # the syntax <hashname>=<hashvalue>, where <hashname> is the
                # lower cased name of the hash function used, and <hashvalue> is
                # the hex encoded digest.
                algorithm, _, hash_ = found_metadata.partition("=")
                metadata = (algorithm.lower(), hash_)
            else:
                # The repository MAY use true as the attribute's value if a hash
                # is unavailable.
                metadata = "", ""
            args["metadata"] = metadata

        self.archive_links.append(args)


def from_project_details_html(html: str, name: str) -> ProjectDetails_1_0:
    """Convert the HTML response for a project details page to a :pep:`691` response.

    Due to HTML project details pages lacking the name of the project, it must
    be specified via the *name* parameter to fill in the JSON data.
    """
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    files: List[ProjectFileDetails_1_0] = []
    for archive_link in parser.archive_links:
        details: ProjectFileDetails_1_0 = {
            "filename": archive_link["filename"],
            "url": archive_link["url"],
            "hashes": {},
        }
        if "hashes" in archive_link:
            details["hashes"] = dict([archive_link["hashes"]])
        if "metadata" in archive_link:
            algorithm, value = archive_link["metadata"]
            if algorithm:
                details["dist-info-metadata"] = {algorithm: value}
            else:
                details["dist-info-metadata"] = True
        for key in {"requires-python", "yanked", "gpg-sig"}:
            if key in archive_link:
                details[key] = archive_link[key]  # type: ignore
        files.append(details)
    return {
        "meta": {"api-version": "1.0"},
        "name": packaging.utils.canonicalize_name(name),
        "files": files,
    }