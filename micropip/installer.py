import asyncio
import logging
from collections.abc import Iterable
from importlib.metadata import Distribution
from pathlib import Path

from ._compat import CompatibilityLayer
from ._utils import get_files_in_distribution, get_root
from .package import PackageMetadata
from .wheelinfo import WheelInfo

logger = logging.getLogger("micropip")


class Installer:
    """
    Installer installs the wheels and lock file packages found by a ``Resolver``,
    and uninstalls distributions.

    All access to the runtime goes through ``compat_layer``. Subclasses can
    override methods such as :meth:`install_wheel` to customize installation.
    """

    def __init__(self, compat_layer: CompatibilityLayer) -> None:
        self.compat_layer = compat_layer

    async def install(
        self,
        wheels: list[WheelInfo],
        pyodide_packages: list[PackageMetadata],
        target: Path,
    ) -> None:
        """Install downloaded ``wheels`` into ``target``, and load ``pyodide_packages``."""
        await asyncio.gather(*(self.install_wheel(wheel, target) for wheel in wheels))

        if pyodide_packages:
            await self.install_pyodide_packages(pyodide_packages)

    async def install_wheel(self, wheel: WheelInfo, target: Path) -> None:
        """
        Install a downloaded wheel into the target directory.

        The installation process is as follows:
            1. The wheel is validated by comparing its hash with the one provided by the package index.
            2. The wheel is extracted to the target directory, and its metadata is set.
            3. The wheel is recorded as loaded.
        """
        wheel.validate_checksum()

        await self.compat_layer.install(
            wheel.data,
            wheel.filename,
            str(target),
            wheel.install_metadata(),
        )

        self.compat_layer.add_loaded_package(wheel.project_name, wheel.source)

    async def install_pyodide_packages(
        self, pyodide_packages: list[PackageMetadata]
    ) -> None:
        """Load packages from the lock file."""
        lockfile = self.compat_layer.lockfile
        if lockfile is None:
            # The resolver only picks packages from the lock file if there is one
            raise RuntimeError(
                "Micropip internal error: attempted to load packages without a lock file"
            )
        await lockfile.load([pkg.name for pkg in pyodide_packages])

    def uninstall(self, distributions: Iterable[Distribution]) -> None:
        """
        Uninstall the given package distributions.

        This function does not do any checks, so make sure that the distributions
        are installed and that they are installed using a wheel file, i.e. packages
        that have distribution metadata.

        This function also does not invalidate the import cache, so make sure to
        call `importlib.invalidate_caches()` after calling this function.
        """
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
                            "skipping file '%s' that is not relative to root",
                            file,
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

            if not self.compat_layer.remove_loaded_package(name):
                # This should not happen, but just in case
                logger.warning("a package '%s' was not found in loadedPackages.", name)

            logger.info("Successfully uninstalled %s-%s", name, version)
