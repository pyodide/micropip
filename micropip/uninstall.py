import importlib
import importlib.metadata
import warnings
from importlib.metadata import Distribution
from pathlib import Path

from ._compat import loadedPackages


def _get_dist_info(dist: Distribution) -> Path:
    """
    Get the .dist-info directory of a distribution.
    """
    return dist._path  # type: ignore[attr-defined]


def _get_root(dist: Distribution) -> Path:
    """
    Get the root directory where a package is installed.
    This is normally the site-packages directory.
    """
    return _get_dist_info(dist).parent


def _get_files_in_distribution(dist: Distribution) -> set[Path]:
    """
    Get a list of files in a distribution, using the metadata.

    Parameters
    ----------
    dist
        Distribution to get files from.

    Returns
    -------
    A list of directories in the distribution. This list is sorted
    in a reverse-hierarchical order, so that directories are listed after
    files that are in them, making it easier to remove directories
    that are empty after uninstallation.
    """

    root = _get_root(dist)
    dist_info = _get_dist_info(dist)

    files_to_remove = set()
    pkg_files = dist.files or []
    metadata_files = dist_info.glob("*")

    for file in pkg_files:
        abspath = (root / file).resolve()

        if not abspath.is_file():
            if not abspath.is_relative_to(root):
                # This file is not in the site-packages directory. Probably one of:
                # - data_files
                # - scripts
                # - entry_points
                # Since we don't support these, we can ignore them (except for data_files (TODO))
                continue

            warnings.warn(
                f"WARNING: A file '{abspath}' listed in the metadata of '{dist.name}' does not exist."
            )

        files_to_remove.add(abspath)

    # Also add all files in the .dist-info directory.
    # Since micropip adds some extra files there, we need to remove them too.
    files_to_remove.update(metadata_files)

    return files_to_remove


def uninstall(packages: str | list[str]) -> None:
    """Uninstall packages.

    We do a lot simpler version of uninstallation than pip does.
    We just remove all files that are listed in the distribution metadata.

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
            warnings.warn(f"WARNING: Skipping '{package}' as it is not installed.")

    for dist in distributions:
        # Note: this value needs to be retrieved before removing files, as
        #       dist.name uses metadata file to get the name
        name = dist.name

        root = _get_root(dist)
        files = _get_files_in_distribution(dist)
        directories = set()

        for file in files:
            file.unlink()

            if file.parent != root:
                directories.add(file.parent)

        # Remove directories in reverse hierarchical order
        for directory in sorted(directories, key=lambda x: len(x.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                warnings.warn(
                    f"WARNING: A directory '{directory}' is not empty after uninstallation of '{name}'."
                )
                print(list(directory.glob("*")))

        if hasattr(loadedPackages, name):
            delattr(loadedPackages, name)
        else:
            # This should not happen, but just in case
            warnings.warn(
                f"WARNING: a package '{name}' was not found in loadedPackages."
            )

    importlib.invalidate_caches()
