from abc import ABC, abstractmethod
from typing import Any


class CompatibilityLayer(ABC):
    """
    CompatibilityLayer is the interface between micropip and the runtime it runs in.

    micropip talks to the runtime (fetching files, installing wheels, reading the
    lock file, ...) only through an instance of this class, which is passed to
    ``PackageManager``. Subclasses must set the lock file attributes (e.g. in
    ``__init__``) and implement all abstract methods.
    """

    lockfile_info: dict[str, str]
    """The ``info`` section of the lock file."""

    lockfile_packages: dict[str, dict[str, Any]]
    """The ``packages`` section of the lock file."""

    lockfile_base_url: str | None = None
    """The base URL that relative file names in the lock file are resolved against."""

    @abstractmethod
    async def fetch_bytes(self, url: str, kwargs: dict[str, Any]) -> bytes:
        """Fetch ``url`` and return the response body."""

    @abstractmethod
    async def fetch_string_and_headers(
        self, url: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, str]]:
        """Fetch ``url`` and return the decoded response body and the response headers."""

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
