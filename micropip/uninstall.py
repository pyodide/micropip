import importlib.metadata
import warnings
from importlib.metadata import Distribution
from pathlib import Path


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
        files = dist.files or []
        # Distribution._path points to .dist-info directory
        root = dist._path.parent  # type: ignore[attr-defined]

        # 1) Remove files

        for file in files:
            file_path = Path(file.locate())
            try:
                file_path.unlink()
            except FileNotFoundError:
                # File was removed manually by user?
                continue

        # 2) Remove directories

        # TODO: also remove directories that are not under sitepackages directory? (e.g. data_files?)
        directories_to_remove = set(dist._path.name)  # type: ignore[attr-defined]
        directories_to_remove |= set(importlib.metadata._top_level_declared(dist))  # type: ignore[attr-defined]
        directories_to_remove |= set(importlib.metadata._top_level_inferred(dist))  # type: ignore[attr-defined]

        for directory in directories_to_remove:
            directory_abs = root / directory
            if not directory_abs.is_dir():
                continue

            try:
                directory_abs.rmdir()
            except OSError:
                warnings.warn(
                    f"The directory '{file_path.parent}' is not empty. The directory will not be removed."
                )
                continue
