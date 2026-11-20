"""
Sources tell micropip where to look for packages.

A source is passed in ``index_urls`` (of :py:func:`micropip.install`,
:py:meth:`micropip.Client.install` or :py:meth:`micropip.Client.set_index_urls`),
alongside plain index URLs. Sources are searched in order.

- A URL string is an :py:class:`IndexSource`, and ``"PYPI"`` is PyPI.
- ``"PYODIDE"`` is a :py:class:`LockFileSource`: the lock file of the
  compatibility layer, searched at that position.
- Any other :py:class:`Source` subclass can be used to look up packages
  somewhere else, e.g. in a file that lists many packages at once.

.. code-block:: python

    class AllJsonSource(Source):
        def __init__(self, url):
            self.url = url
            self._data = None

        async def get_project(self, name, fetch):
            if self._data is None:
                self._data = json.loads((await fetch(self.url)).text())
            project = self._data.get(name)
            if project is None:
                return None
            return ProjectPage.from_json_api(project, base_url=self.url, name=name)

    # Look in all.json, then in the Pyodide lock file, and never on PyPI
    await micropip.install("pkg", index_urls=[AllJsonSource(url), "PYODIDE"])
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from ._compat import FetchResponse
from .package_index import (
    PYODIDE,
    PYPI,
    PYPI_URL,
    ProjectFile,
    ProjectPage,
    project_urls,
)

Fetch = Callable[..., Awaitable[FetchResponse]]
"""
``await fetch(url, headers=None)``: fetches ``url`` through the compatibility
layer, with the fetch options of the current install (e.g. ``credentials``).
``headers`` are added to the request.
"""

# Prefer the Simple JSON API over the Simple HTML API or the JSON API
_INDEX_ACCEPT = "application/vnd.pypi.simple.v1+json, */*;q=0.01"


class Source(ABC):
    """Where micropip looks up the files of a project."""

    @abstractmethod
    async def get_project(self, name: str, fetch: Fetch) -> ProjectPage | None:
        """
        Return the files of the project ``name`` (a canonicalized name), or
        ``None`` if this source doesn't have the project.

        ``fetch`` fetches a URL through the compatibility layer. Use it, rather
        than fetching directly, so that custom compatibility layers and fetch
        options (e.g. ``credentials``) apply.
        """


class IndexSource(Source):
    """
    A package index that supports the Simple repository API (HTML or JSON) or
    the JSON API.

    The URL may contain a ``{package_name}`` placeholder. Otherwise, the package
    name is appended to it.
    """

    def __init__(self, url: str) -> None:
        self.url = PYPI_URL if url == PYPI else url

    def __repr__(self) -> str:
        return f"IndexSource({self.url!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IndexSource) and other.url == self.url

    def __hash__(self) -> int:
        return hash(self.url)

    async def get_project(self, name: str, fetch: Fetch) -> ProjectPage | None:
        (url,) = project_urls(name, [self.url])
        try:
            response = await fetch(url, headers={"accept": _INDEX_ACCEPT})
        except Exception:
            # Not found (or unreachable): try the next source
            return None
        return ProjectPage.from_response(name, url, response.text(), response.headers)


class LockFileSource(Source):
    """
    The lock file of the compatibility layer (``"PYODIDE"`` in ``index_urls``).

    Packages in the lock file are not installed from files, so micropip handles
    this source itself and never calls :py:meth:`get_project`.
    """

    def __repr__(self) -> str:
        return "LockFileSource()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LockFileSource)

    def __hash__(self) -> int:
        return hash(LockFileSource)

    async def get_project(self, name: str, fetch: Fetch) -> ProjectPage | None:
        raise NotImplementedError("The lock file is handled by the resolver.")


def to_source(entry: "str | Source") -> Source:
    """Turn an ``index_urls`` entry into a :py:class:`Source`."""
    if isinstance(entry, Source):
        return entry
    if entry == PYODIDE:
        return LockFileSource()
    return IndexSource(entry)


__all__ = [
    "Fetch",
    "IndexSource",
    "LockFileSource",
    "ProjectFile",
    "ProjectPage",
    "Source",
]
