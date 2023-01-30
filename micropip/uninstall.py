import importlib.metadata
import warnings
from importlib.metadata import Distribution
from pathlib import Path
import shutil

from ._importlib_helpers import _top_level_declared, _top_level_inferred


def uninstall(packages: str | list[str]) -> None:
    """Uninstall packages.

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
            raise RuntimeError(f"The package '{package}' is not installed") from None

    for dist in distributions:
        # Distribution._path points to .dist-info directory
        root = dist._path.parent  # type: ignore[attr-defined]

        # TODO: also remove directories that are not under sitepackages directory? (e.g. data_files?)
        directories_to_remove = set(dist._path.name)  # type: ignore[attr-defined]
        directories_to_remove |= set(_top_level_declared(dist))
        directories_to_remove |= set(_top_level_inferred(dist))

        for directory in directories_to_remove:
            path = root / directory
            try:
                shutil.rmtree(path, ignore_errors=False)
            # File not found error is okay, while other errors need to be reported
            except FileNotFoundError:
                pass