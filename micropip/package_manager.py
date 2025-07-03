import asyncio
import builtins
import importlib
import importlib.metadata
import logging
from collections.abc import Iterable
from importlib.metadata import Distribution
from pathlib import Path
from typing import (  # noqa: UP035 List import is necessary due to the `list` method
    List,
)

from . import _mock_package, package_index
from ._compat import CompatibilityLayer, compatibility_layer
from ._utils import get_files_in_distribution, get_root
from ._vendored.packaging.src.packaging.markers import default_environment
from .constants import FAQ_URLS
from .freeze import freeze_lockfile
from .logging import indent_log, setup_logging
from .package import PackageDict, PackageMetadata
from .transaction import Transaction


class PackageManager:
    """
    PackageManager provides an extensible interface for customizing micropip's behavior.

    Each Manager instance holds its own local state that is
    independent of other instances.
    """

    def __init__(self, compat: type[CompatibilityLayer] | None = None) -> None:

        if compat is None:
            compat = compatibility_layer

        self.index_urls = package_index.DEFAULT_INDEX_URLS[:]
        self.compat_layer: type[CompatibilityLayer] = compat
        self.constraints: list[str] = []

        pass

    async def install(
        self,
        requirements: str | list[str],
        keep_going: bool = False,
        deps: bool = True,
        credentials: str | None = None,
        pre: bool = False,
        index_urls: list[str] | str | None = None,
        *,
        constraints: list[str] | None = None,
        reinstall: bool = False,
        verbose: bool | int | None = None,
    ) -> None:
        """Install the given package and all of its dependencies.

        If a package is not found in the Pyodide repository it will be loaded from
        PyPI. Micropip can only load pure Python wheels or wasm32/emscripten wheels
        built by Pyodide.

        When used in web browsers, downloads from PyPI will be cached. When run in
        Node.js, packages are currently not cached, and will be re-downloaded each
        time ``micropip.install`` is run.

        Parameters
        ----------
        requirements:

            A requirement or list of requirements to install. Each requirement is a
            string, which should be either a package name or a wheel URI:

            - If the requirement does not end in ``.whl``, it will be interpreted as \
            a package name. A package with this name must either be present \
            in the Pyodide lock file or on PyPI.

            - If the requirement ends in ``.whl``, it is a wheel URI. The part of \
            the requirement after the last ``/``  must be a valid wheel name in \
            compliance with the `PEP 427 naming convention \
            <https://www.python.org/dev/peps/pep-0427/#file-format>`_.

            - If a wheel URI starts with ``emfs:``, it will be interpreted as a path \
            in the Emscripten file system (Pyodide's file system). E.g., \
            ``emfs:../relative/path/wheel.whl`` or ``emfs:/absolute/path/wheel.whl``. \
            In this case, only .whl files are supported.

            - If a wheel URI requirement starts with ``http:`` or ``https:`` it will \
            be interpreted as a URL.

            - In node, you can access the native file system using a URI that starts \
            with ``file:``. In the browser this will not work.

        keep_going:

            This parameter decides the behavior of the micropip when it encounters a
            Python package without a pure Python wheel while doing dependency
            resolution:

            - If ``False``, an error will be raised on first package with a missing \
            wheel.

            - If ``True``, the micropip will keep going after the first error, and \
            report a list of errors at the end.

        deps:

            If ``True``, install dependencies specified in METADATA file for each
            package. Otherwise do not install dependencies.

        credentials:

            This parameter specifies the value of ``credentials`` when calling the
            `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__
            function which is used to download the package.

            When not specified, ``fetch()`` is called without ``credentials``.

        pre:

            If ``True``, include pre-release and development versions. By default,
            micropip only finds stable versions.

        index_urls:

            A list of URLs or a single URL to use as the package index when looking
            up packages. If None, *https://pypi.org/pypi/{package_name}/json* is used.

            - The index URL should support the \
            `JSON API <https://warehouse.pypa.io/api-reference/json/>`__ .

            - The index URL may contain the placeholder {package_name} which will be \
            replaced with the package name when looking up a package. If it does not \
            contain the placeholder, the package name will be appended to the URL.

            - If a list of URLs is provided, micropip will try each URL in order until \
            it finds a package. If no package is found, an error will be raised.

        constraints:

            A list of requirements with versions/URLs which will be used only if
            needed by any ``requirements``.

            Unlike ``requirements``, the package name _must_ be provided in the
            PEP-508 format e.g. ``pkgname@https://...``.

        reinstall:

            If ``False`` (default), micropip will show an error if the requested package
            is already installed, but with a incompatible version. If ``True``,
            micropip will uninstall the existing packages that are not compatible with
            the requested version and install the packages again.

            Note that packages that are already imported will not be reloaded, so make
            sure to reload the module after reinstalling by e.g. running importlib.reload(module).

        verbose:
            Print more information about the process. By default, micropip does not
            change logger level. Setting ``verbose=True`` will print similar
            information as pip.
        """

        with setup_logging().ctx_level(verbose) as logger:
            if index_urls is None:
                index_urls = self.index_urls

            if constraints is None:
                constraints = self.constraints

            ctx = default_environment()
            if isinstance(requirements, str):
                requirements = [requirements]

            fetch_kwargs = {}

            if credentials:
                fetch_kwargs["credentials"] = credentials

            # Note: getsitepackages is not available in a virtual environment...
            # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
            # problem is not fixed)
            from site import getsitepackages

            wheel_base = Path(getsitepackages()[0])

            transaction = Transaction(
                _compat_layer=self.compat_layer,
                ctx=ctx,  # type: ignore[arg-type]
                ctx_extras=[],
                keep_going=keep_going,
                deps=deps,
                pre=pre,
                fetch_kwargs=fetch_kwargs,
                verbose=verbose,
                index_urls=index_urls,
                constraints=constraints,
                reinstall=reinstall,
            )
            await transaction.gather_requirements(requirements)

            if transaction.failed:
                failed_requirements = ", ".join(
                    [f"'{req}'" for req in transaction.failed]
                )
                raise ValueError(
                    f"Can't find a pure Python 3 wheel for: {failed_requirements}\n"
                    f"See: {FAQ_URLS['cant_find_wheel']}\n"
                )

            pyodide_packages, wheels = transaction.pyodide_packages, transaction.wheels

            packages_all = [pkg.name for pkg in wheels + pyodide_packages]

            distributions = search_installed_packages(packages_all)
            # This check is redundant because the distributions will always be an empty list when reinstall==False
            # (no installed packages will be returned from transaction)
            # But just in case.
            if reinstall:
                with indent_log():
                    self._uninstall_distributions(distributions, logger)

            logger.debug(
                "Installing packages %r and wheels %r ",
                transaction.pyodide_packages,
                [w.filename for w in transaction.wheels],
            )

            if packages_all:
                logger.info(
                    "Installing collected packages: %s", ", ".join(packages_all)
                )

            # Install PyPI packages
            # detect whether the wheel metadata is from PyPI or from custom location
            # wheel metadata from PyPI has SHA256 checksum digest.
            await asyncio.gather(*(wheel.install(wheel_base) for wheel in wheels))

            # Install built-in packages
            if pyodide_packages:
                # Note: branch never happens in out-of-browser testing because in
                # that case LOCKFILE_PACKAGES is empty.
                await asyncio.ensure_future(
                    self.compat_layer.loadPackage(
                        self.compat_layer.to_js(
                            [name for [name, _, _] in pyodide_packages]
                        )
                    )
                )

            packages = [
                f"{pkg.name}-{pkg.version}" for pkg in pyodide_packages + wheels
            ]

            if packages:
                logger.info("Successfully installed %s", ", ".join(packages))

            importlib.invalidate_caches()

    def list_packages(self) -> PackageDict:
        """Get the dictionary of installed packages.

        Returns
        -------
        ``PackageDict``
            A dictionary of installed packages.

            >>> import micropip
            >>> await micropip.install('regex') # doctest: +SKIP
            >>> package_list = micropip.list()
            >>> print(package_list) # doctest: +SKIP
            Name              | Version  | Source
            ----------------- | -------- | -------
            regex             | 2021.7.6 | pyodide
            >>> "regex" in package_list # doctest: +SKIP
            True
        """
        # Add packages that are loaded through pyodide.loadPackage
        packages = PackageDict()
        for dist in importlib.metadata.distributions():
            name = dist.name
            version = dist.version
            source = dist.read_text("PYODIDE_SOURCE")
            if source is None:
                # source is None if PYODIDE_SOURCE does not exist. In this case the
                # wheel was installed manually, not via `pyodide.loadPackage` or
                # `micropip`.
                continue
            packages[name] = PackageMetadata(
                name=name,
                version=version,
                source=source,
            )

        for name, pkg_source in self.compat_layer.loadedPackages.to_py().items():
            if name in packages:
                continue

            if name in self.compat_layer.lockfile_packages:
                version = self.compat_layer.lockfile_packages[name]["version"]
                source_ = "pyodide"
                if pkg_source != "default channel":
                    # Pyodide package loaded from a custom URL
                    source_ = pkg_source
            else:
                # TODO: calculate version from wheel metadata
                version = "unknown"
                source_ = pkg_source
            packages[name] = PackageMetadata(name=name, version=version, source=source_)
        return packages

    def freeze(self) -> str:
        """Produce a json string which can be used as the contents of the
        ``pyodide-lock.json`` lock file.

        If you later load Pyodide with this lock file, you can use
        :js:func:`pyodide.loadPackage` to load packages that were loaded with :py:mod:`micropip`
        this time. Loading packages with :js:func:`~pyodide.loadPackage` is much faster
        and you will always get consistent versions of all your dependencies.

        You can use your custom lock file by passing an appropriate url to the
        ``lockFileURL`` of :js:func:`~globalThis.loadPyodide`.
        """
        return freeze_lockfile(
            self.compat_layer.lockfile_packages, self.compat_layer.lockfile_info
        )

    def add_mock_package(
        self,
        name: str,
        version: str,
        *,
        modules: dict[str, str | None] | None = None,
        persistent: bool = False,
    ):
        """
        Add a mock version of a package to the package dictionary.

        This means that if it is a dependency, it is skipped on install.

        By default a single empty module is installed with the same
        name as the package. You can alternatively give one or more modules to make a
        set of named modules.

        The modules parameter is usually a dictionary mapping module name to module text.

        .. code-block:: python

            {
                "mylovely_module":'''
                def module_method(an_argument):
                    print("This becomes a module level argument")

                module_value = "this value becomes a module level variable"
                print("This is run on import of module")
                '''
            }

        If you are adding the module in non-persistent mode, you can also pass functions
        which are used to initialize the module on loading (as in `importlib.abc.loader.exec_module` ).
        This allows you to do things like use `unittest.mock.MagicMock` classes for modules.

        .. code-block:: python

            def init_fn(module):
                module.dict["WOO"]="hello"
                print("Initing the module now!")

            ...

            {
                "mylovely_module": init_fn
            }

        Parameters
        ----------
        name :

            Package name to add

        version :

            Version of the package. This should be a semantic version string,
            e.g. 1.2.3

        modules :

            Dictionary of module_name:string pairs.
            The string contains the source of the mock module or is blank for
            an empty module.

        persistent :

            If this is True, modules will be written to the file system, so they
            persist between runs of python (assuming the file system persists).
            If it is False, modules will be stored inside micropip in memory only.
        """
        return _mock_package.add_mock_package(
            name, version, modules=modules, persistent=persistent
        )

    def list_mock_packages(self):
        """
        List all mock packages currently installed.
        """
        return _mock_package.list_mock_packages()

    def remove_mock_package(self, name: str):
        """
        Remove a mock package.
        """
        return _mock_package.remove_mock_package(name)

    def uninstall(
        self, packages: str | builtins.list[str], *, verbose: bool | int = False
    ) -> None:
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

            self._uninstall_distributions(distributions, logger)

            importlib.invalidate_caches()

    def set_index_urls(self, urls: List[str] | str):  # noqa: UP006
        """
        Set the index URLs to use when looking up packages.

        - The index URL should support the
            `JSON API <https://warehouse.pypa.io/api-reference/json/>`__ .

        - The index URL may contain the placeholder {package_name} which will be
            replaced with the package name when looking up a package. If it does not
            contain the placeholder, the package name will be appended to the URL.

        - If a list of URLs is provided, micropip will try each URL in order until
            it finds a package. If no package is found, an error will be raised.

        Parameters
        ----------
        urls
            A list of URLs or a single URL to use as the package index.
        """

        if isinstance(urls, str):
            urls = [urls]

        self.index_urls = urls[:]

    def set_constraints(self, constraints: List[str]):  # noqa: UP006
        """
        Set the default constraints to use when looking up packages.

        Parameters
        ----------
        constraints
            A list of PEP-508 requirements, each of which must include a name and
            version, but no ``[extras]``.
        """

        self.constraints = constraints[:]

    def _uninstall_distributions(
        self,
        distributions: Iterable[Distribution],
        logger: logging.Logger,  # TODO: move this to an attribute of the PackageManager
    ) -> None:
        """
        Uninstall the given package distributions.

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

            if hasattr(self.compat_layer.loadedPackages, name):
                delattr(self.compat_layer.loadedPackages, name)
            else:
                # This should not happen, but just in case
                logger.warning("a package '%s' was not found in loadedPackages.", name)

            logger.info("Successfully uninstalled %s-%s", name, version)


def search_installed_packages(
    names: list[str],
) -> list[importlib.metadata.Distribution]:
    """
    Get installed packages by name.
    Parameters
    ----------
    names
        List of distribution names to search for.
    Returns
    -------
    List of distributions that were found.
    If a distribution is not found, it is not included in the list.
    """
    distributions = []
    for name in names:
        try:
            distributions.append(importlib.metadata.distribution(name))
        except importlib.metadata.PackageNotFoundError:
            pass

    return distributions
