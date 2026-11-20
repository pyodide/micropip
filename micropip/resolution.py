"""
The result of resolving requirements, and of installing them.

See :py:meth:`micropip.Client.resolve` and
:py:meth:`micropip.Client.install_resolution`.
"""

from dataclasses import dataclass, field

from ._vendored.packaging.src.packaging.requirements import Requirement
from .package import PackageMetadata
from .wheelinfo import WheelInfo


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


__all__ = ["InstallResult", "Resolution"]
