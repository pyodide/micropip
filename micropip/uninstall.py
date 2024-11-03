import importlib
import importlib.metadata
from importlib.metadata import Distribution

from ._compat import loadedPackages
from ._utils import get_files_in_distribution, get_root
from .logging import setup_logging


def uninstall(packages: str | list[str], *, verbose: bool | int = False) -> None:
    with setup_logging().ctx_level(verbose) as logger:

        if isinstance(packages, str):
            packages = [packages]

        distributions: list[Distribution] = []
        for package in packages:
            try:
                dist = importlib.metadata.distribution(package)
                distributions.append(dist)
            except importlib.metadata.PackageNotFoundError:
                logger.warning("Skipping '%s' as it is not installed.", package)

        for dist in distributions:
            # Note: this value needs to be retrieved before removing files, as
            #       dist.name uses metadata file to get the name
            name = dist.name
            version = dist.version

            logger.info("Found existing installation: %s %s", name, version)

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
                        logger.warning(
                            "skipping file '%s' that is relative to root",
                        )
                        continue
                    # see PR 130, it is likely that this is never triggered since Python 3.12
                    # as non existing files are not listed by get_files_in_distribution anymore.
                    logger.warning(
                        "A file '%s' listed in the metadata of '%s' does not exist.",
                        file,
                        name,
                    )

                    continue

                file.unlink()

                if file.parent != root:
                    directories.add(file.parent)

            # Remove directories in reverse hierarchical order
            for directory in sorted(
                directories, key=lambda x: len(x.parts), reverse=True
            ):
                try:
                    directory.rmdir()
                except OSError:
                    logger.warning(
                        "A directory '%s' is not empty after uninstallation of '%s'. "
                        "This might cause problems when installing a new version of the package. ",
                        directory,
                        name,
                    )

            if hasattr(loadedPackages, name):
                delattr(loadedPackages, name)
            else:
                # This should not happen, but just in case
                logger.warning("a package '%s' was not found in loadedPackages.", name)

            logger.info("Successfully uninstalled %s-%s", name, version)

        importlib.invalidate_caches()
