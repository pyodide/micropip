import importlib
import importlib.metadata
import warnings
from collections.abc import Iterable
from importlib.metadata import Distribution

from .._uninstall import _uninstall


def uninstall(packages: str | Iterable[str]) -> None:
    """Uninstall the given packages.

    This function only supports uninstalling packages that are installed
    using a wheel file, i.e. packages that have distribution metadata.

    It is possible to reinstall a package after uninstalling it, but
    note that modules / functions that are already imported will not be
    automatically removed from the namespace. So make sure to reload
    the module after reinstalling by e.g. running `importlib.reload(module)`.

    Parameters
    ----------
    packages
        Packages to uninstall.
    """

    if isinstance(packages, str):
        packages = [packages]

    distributions: list[Distribution] = []
    for package in packages:
        try:
            dist = importlib.metadata.distribution(package)
            distributions.append(dist)
        except importlib.metadata.PackageNotFoundError:
            warnings.warn(
                f"WARNING: Skipping '{package}' as it is not installed.",
                stacklevel=1,
            )

    _uninstall(distributions)

    importlib.invalidate_caches()
