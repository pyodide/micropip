"""
The result of resolving requirements, and of installing them.

See :py:meth:`micropip.Client.resolve` and
:py:meth:`micropip.Client.install_resolution`.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._compat import FetchOptions
from ._vendored.packaging.src.packaging.requirements import Requirement
from .package import PackageMetadata
from .package_index import DEFAULT_INDEX_URLS
from .wheelinfo import WheelInfo

if TYPE_CHECKING:
    from .sources import Source


@dataclass
class ResolveRequest:
    """
    What to resolve, and how. Passed to the resolver (see
    :py:attr:`micropip.Client.resolver_class`). The fields match the arguments
    of :py:meth:`micropip.Client.install`.
    """

    requirements: list[str] = field(default_factory=list)
    """Requirements to resolve: PEP 508 strings or wheel URLs."""

    index_urls: "list[str | Source] | str" = field(
        default_factory=lambda: list["str | Source"](DEFAULT_INDEX_URLS)
    )
    """Index URLs and :py:class:`~micropip.sources.Source` objects, searched in order."""

    constraints: list[str] = field(default_factory=list)
    keep_going: bool = False
    deps: bool = True
    pre: bool = False
    reinstall: bool = False

    fetch_options: FetchOptions = field(default_factory=FetchOptions)
    """Fetch options for all requests (package index pages, wheels and their metadata)."""

    environment: dict[str, str] | None = None
    """Environment markers (PEP 508) to evaluate requirements with. Defaults to the current environment."""

    verbose: bool | int | None = None


@dataclass
class Resolution:
    """
    The packages to install for a set of requirements, as returned by
    :py:meth:`micropip.Client.resolve`. Pass it to
    :py:meth:`micropip.Client.install_resolution` to install them.
    """

    wheels: list[WheelInfo] = field(default_factory=list)
    """Wheels to install. ``name``, ``version``, ``filename`` and ``url`` are stable."""

    lockfile_packages: list[PackageMetadata] = field(default_factory=list)
    """Packages to load from the lock file of the compatibility layer."""

    failed: list[Requirement] = field(default_factory=list)
    """
    Requirements that could not be resolved. Only non-empty when resolving with
    ``keep_going=True``; the other packages can still be installed.
    """

    reinstall: bool = False
    """Whether installed versions of these packages are uninstalled first."""

    requested_by: dict[str, list[str]] = field(default_factory=dict)
    """
    For each package to install (by canonicalized name), the top-level
    requirements (as passed to ``resolve()``) that pulled it in.
    """

    @property
    def packages(self) -> list[PackageMetadata]:
        """All packages to install, from wheels and from the lock file."""
        return [
            PackageMetadata(
                name=wheel.name, version=str(wheel.version), source=wheel.source
            )
            for wheel in self.wheels
        ] + list(self.lockfile_packages)


@dataclass
class InstallResult:
    """
    The outcome of installing one package, as yielded by
    :py:meth:`micropip.Client.install_resolution`.
    """

    name: str
    version: str
    source: str
    """Where the package was installed from: ``"pyodide"`` (the lock file), ``"pypi"`` or a URL."""
    error: BaseException | None = None
    """The error that made the installation fail, or ``None`` if it succeeded."""

    @property
    def ok(self) -> bool:
        return self.error is None


__all__ = ["InstallResult", "ResolveRequest", "Resolution"]
