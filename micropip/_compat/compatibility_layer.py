from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchOptions:
    """Options for :py:meth:`CompatibilityLayer.fetch`.

    New fields may be added over time, always with a default value.
    """

    headers: dict[str, str] = field(default_factory=dict)
    """Request headers to send."""

    credentials: str | None = None
    """
    The ``credentials`` option of the
    `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__ API.
    """

    extra: dict[str, Any] = field(default_factory=dict)
    """
    Runtime-specific options, passed to the runtime's fetch function as they are
    (e.g. ``{"cache": "no-store"}`` for ``pyfetch`` in Pyodide).
    """


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
class LockedPackage:
    """A package in a :py:class:`LockFile`."""

    name: str
    version: str
    depends: list[str] = field(default_factory=list)
    """Names of the packages this package depends on."""


class LockFile(ABC):
    """
    A set of prebuilt packages that the runtime can load directly, without
    looking them up on a package index (e.g. Pyodide's ``pyodide-lock.json``).

    A :py:class:`CompatibilityLayer` may provide one as its :py:attr:`~CompatibilityLayer.lockfile`.
    micropip looks requirements up in it, loads the packages it finds with
    :py:meth:`load`, and uses :py:meth:`freeze` for ``micropip.freeze()``.
    The format of the lock file is up to the implementation.
    """

    @abstractmethod
    def get(self, name: str) -> LockedPackage | None:
        """Return the package ``name`` (a canonicalized name), or ``None`` if it is not in the lock file."""

    @abstractmethod
    async def load(self, names: list[str]) -> list[str]:
        """
        Load the packages ``names`` from the lock file into the runtime.

        Return the names (of those in ``names``) that are loaded after the call,
        including ones that were already loaded. A name that is missing failed
        to load.
        """

    @abstractmethod
    def freeze(self) -> str:
        """
        Return a new lock file, in the same format, that also contains the
        packages installed with micropip.
        """


class CompatibilityLayer(ABC):
    """
    CompatibilityLayer is the interface between micropip and the runtime it runs in.

    micropip talks to the runtime (fetching files, installing wheels, reading the
    lock file, ...) only through an instance of this class, which is passed to
    :py:class:`micropip.Client`. Subclasses must implement all abstract methods,
    and may set :py:attr:`lockfile`.

    To change only part of the default behavior in Pyodide, subclass
    :py:class:`micropip.compat.PyodideCompatibilityLayer` instead.
    """

    lockfile: LockFile | None = None
    """
    The lock file of the runtime, if it has one. Without a lock file, all
    packages are looked up on the package indexes, and ``micropip.freeze()``
    is not available.
    """

    @abstractmethod
    async def fetch(self, url: str, options: FetchOptions) -> FetchResponse:
        """Fetch ``url``.

        Used both for package index pages and for wheel files.

        Implementations should ignore fields of ``options`` that they don't
        support, so that new fields can be added without breaking them.

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
    def loaded_packages(self) -> dict[str, str]:
        """Return a mapping from the name of each loaded package to its source."""

    @abstractmethod
    def add_loaded_package(self, name: str, source: str) -> None:
        """Record that the package ``name`` was installed from ``source``."""

    @abstractmethod
    def remove_loaded_package(self, name: str) -> bool:
        """Forget the package ``name``. Return ``False`` if it was not recorded."""
