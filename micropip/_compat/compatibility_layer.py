from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResponse:
    """The result of :py:meth:`CompatibilityLayer.fetch`."""

    content: bytes
    """The response body."""

    headers: dict[str, str] = field(default_factory=dict)
    """The response headers, with lower-case names."""

    def text(self) -> str:
        """The response body decoded as UTF-8."""
        return self.content.decode("utf-8", errors="replace")


@dataclass
class LockFile:
    """The Pyodide lock file (``pyodide-lock.json``) that the runtime was loaded with."""

    info: dict[str, Any] = field(default_factory=dict)
    """The ``info`` section of the lock file."""

    packages: dict[str, dict[str, Any]] = field(default_factory=dict)
    """The ``packages`` section of the lock file, keyed by package name."""

    base_url: str | None = None
    """The base URL that relative file names in the lock file are resolved against."""


class CompatibilityLayer(ABC):
    """
    CompatibilityLayer is the interface between micropip and the runtime it runs in.

    micropip talks to the runtime (fetching files, installing wheels, reading the
    lock file, ...) only through an instance of this class, which is passed to
    :py:class:`micropip.Client`. Subclasses must set :py:attr:`lockfile` (e.g. in
    ``__init__``) and implement all abstract methods.

    To change only part of the default behavior in Pyodide, subclass
    :py:class:`micropip.compat.PyodideCompatibilityLayer` instead.
    """

    lockfile: LockFile
    """The lock file of the runtime. Packages in it can be loaded with :py:meth:`load_packages`."""

    @abstractmethod
    async def fetch(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        credentials: str | None = None,
    ) -> FetchResponse:
        """Fetch ``url``.

        Used both for package index pages and for wheel files.

        Parameters
        ----------
        url
            The URL to fetch.
        headers
            Request headers to send.
        credentials
            The ``credentials`` option of the
            `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__
            API, if the user passed one to ``micropip.install``.

        Raises an exception if the request fails, including for HTTP error
        statuses.
        """

    @abstractmethod
    async def install(
        self,
        data: bytes,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Install the wheel ``data`` (named ``filename``) into ``install_dir``.

        ``metadata`` is written as extra files into the ``.dist-info`` directory.
        """

    @abstractmethod
    async def load_packages(self, names: list[str]) -> None:
        """Load packages from the lock file by name."""

    @abstractmethod
    def loaded_packages(self) -> dict[str, str]:
        """Return a mapping from the name of each loaded package to its source."""

    @abstractmethod
    def add_loaded_package(self, name: str, source: str) -> None:
        """Record that the package ``name`` was installed from ``source``."""

    @abstractmethod
    def remove_loaded_package(self, name: str) -> bool:
        """Forget the package ``name``. Return ``False`` if it was not recorded."""
