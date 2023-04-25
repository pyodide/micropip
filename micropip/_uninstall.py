import warnings
from collections.abc import Iterable
from importlib.metadata import Distribution

from ._compat import loadedPackages
from ._utils import get_files_in_distribution, get_root


def uninstall_distributions(distributions: Iterable[Distribution]) -> None:
    """Uninstall the given package distributions.

    This function does not do any checks, so make sure that the distributions
    are installed and that they are installed using a wheel file, i.e. packages
    that have distribution metadata.

    This function also does not invalidate the import cache, so make sure to
    call `importlib.invalidate_caches()` after calling this function.

    Parameters
    ----------
    distributions
        Package distributions to uninstall.
    """

    for dist in distributions:
        # Note: this value needs to be retrieved before removing files, as
        #       dist.name uses metadata file to get the name
        name = dist.name

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

                warnings.warn(
                    f"WARNING: A file '{file}' listed in the metadata of '{dist.name}' does not exist.",
                    stacklevel=1,
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
                warnings.warn(
                    f"WARNING: A directory '{directory}' is not empty after uninstallation of '{name}'. "
                    "This might cause problems when installing a new version of the package. ",
                    stacklevel=1,
                )

        if hasattr(loadedPackages, name):
            delattr(loadedPackages, name)
        else:
            # This should not happen, but just in case
            warnings.warn(
                f"WARNING: a package '{name}' was not found in loadedPackages.",
                stacklevel=1,
            )
