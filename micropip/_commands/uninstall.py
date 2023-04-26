import importlib
import importlib.metadata
from importlib.metadata import Distribution

from .._compat import loadedPackages
from .._utils import get_files_in_distribution, get_root
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

    for dist in distributions:
        # Note: this value needs to be retrieved before removing files, as
        #       dist.name uses metadata file to get the name
        name = dist.name
        version = dist.version

        logger.info(f"Found existing installation: {name} {version}")

        root = get_root(dist)
        files = get_files_in_distribution(dist)
        directories = set()

        for file in files:
            if not file.is_file():
                if not file.is_relative_to(root):
                    # This file is not in the site-packages directory. Probably one of:
                    # - data_files
                    # - scripts
                    # - entry_points
                    # Since we don't support these, we can ignore them (except for data_files (TODO))
                    continue

                logger.warning(
                    f"A file '{file}' listed in the metadata of '{name}' does not exist.",
                )

                continue

            file.unlink()

            if file.parent != root:
                directories.add(file.parent)

        # Remove directories in reverse hierarchical order
        for directory in sorted(directories, key=lambda x: len(x.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                logger.warning(
                    f"A directory '{directory}' is not empty after uninstallation of '{name}'. "
                    "This might cause problems when installing a new version of the package. ",
                )

        if hasattr(loadedPackages, name):
            delattr(loadedPackages, name)
        else:
            # This should not happen, but just in case
            logger.warning(
                f"a package '{name}' was not found in loadedPackages.",
            )

        logger.info(f"Successfully uninstalled {name}-{version}")

    importlib.invalidate_caches()
