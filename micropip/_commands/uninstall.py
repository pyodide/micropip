import importlib
import importlib.metadata
from importlib.metadata import Distribution

from .._uninstall import uninstall_distributions
from ..logging import setup_logging


def uninstall(packages: str | list[str], *, verbose: bool | int = False) -> None:
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

    verbose
        Print more information about the process.
        By default, micropip is silent. Setting ``verbose=True`` will print
        similar information as pip.
    """
    logger = setup_logging(verbose)

    if isinstance(packages, str):
        packages = [packages]

    distributions: list[Distribution] = []
    for package in packages:
        try:
            dist = importlib.metadata.distribution(package)
            distributions.append(dist)
        except importlib.metadata.PackageNotFoundError:
            logger.warning(f"Skipping '{package}' as it is not installed.")

    uninstall_distributions(distributions)

    importlib.invalidate_caches()
