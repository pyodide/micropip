import asyncio
import builtins
import importlib
import importlib.metadata
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
from .logging import setup_logging
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
        self.extra_index_urls: list[str] = []
        self.index_strategy = "first-index"  # default strategy
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
        extra_index_urls: list[str] | str | None = None,
        index_strategy: str | None = None,
        constraints: list[str] | None = None,
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

        extra_index_urls:

            A list of URLs or a single URL to use as additional package indexes when looking
            up packages. Unlike `index_urls`, these are used in addition to the default
            indexes, not instead of them. This is useful for finding packages that may not
            be available in the main package index that is queried by `index_urls`.

            - The format and behaviour of each URL is the same as for `index_urls`.

        index_strategy:

            Determines how package versions are selected when they appear in multiple indexes:

            - ``first-index`` (default): Search for each package across all indexes, limiting \
            the candidate versions to those present in the first index that contains the package.

            - ``unsafe-first-match``: Search for each package across all indexes, but prefer \
            the first index with a compatible version, even if newer versions are available \
            on other indexes.

            - ``unsafe-best-match``: Search for each package across all indexes, and select \
            the best version from the combined set of candidate versions (pip's default).

        constraints:

            A list of requirements with versions/URLs which will be used only if
            needed by any ``requirements``.

            Unlike ``requirements``, the package name _must_ be provided in the
            PEP-508 format e.g. ``pkgname@https://...``.

        verbose:
            Print more information about the process. By default, micropip does not
            change logger level. Setting ``verbose=True`` will print similar
            information as pip.
        """

        with setup_logging().ctx_level(verbose) as logger:
            if index_urls is None:
                index_urls = self.index_urls
                base_index_urls = self.index_urls
            else:
                base_index_urls = (
                    index_urls if isinstance(index_urls, list) else [index_urls]
                )

            if extra_index_urls is None:
                extra_urls = self.extra_index_urls
            else:
                extra_urls = (
                    extra_index_urls
                    if isinstance(extra_index_urls, list)
                    else [extra_index_urls]
                )

            combined_index_urls = base_index_urls + extra_urls

            strategy = (
                index_strategy if index_strategy is not None else self.index_strategy
            )

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
                ctx=ctx,  # type: ignore[arg-type]
                ctx_extras=[],
                keep_going=keep_going,
                deps=deps,
                pre=pre,
                fetch_kwargs=fetch_kwargs,
                verbose=verbose,
                index_urls=combined_index_urls,
                constraints=constraints,
                index_strategy=strategy,
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

            package_names = [pkg.name for pkg in wheels + pyodide_packages]

            logger.debug(
                "Installing packages %r and wheels %r ",
                transaction.pyodide_packages,
                [w.filename for w in transaction.wheels],
            )

            if package_names:
                logger.info(
                    "Installing collected packages: %s", ", ".join(package_names)
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

    def set_extra_index_urls(self, urls: List[str] | str):  # noqa: UP006
        """
        Set the extra index URLs to use when looking up packages.

        These URLs are used in addition to the default index URLs, not instead of them.
        This is useful for finding packages that may not be available in the main
        package index.

        - The index URL should support the \
            `JSON API <https://warehouse.pypa.io/api-reference/json/>`__ .

        - The index URL may contain the placeholder {package_name} which will be \
            replaced with the package name when looking up a package. If it does not \
            contain the placeholder, the package name will be appended to the URL.

        Parameters
        ----------
        urls
            A list of URLs or a single URL to use as extra package indexes.
        """

        if isinstance(urls, str):
            urls = [urls]

        self.extra_index_urls = urls[:]

    def set_index_strategy(self, strategy: str):
        """
        Set the index strategy to use when resolving packages from multiple indexes.

        Parameters
        ----------
        strategy
            The index strategy to use. Valid values are:

            - ``first-index``: Search for each package across all indexes, limiting \
            the candidate versions to those present in the first index that contains the package.

            - ``unsafe-first-match``: Search for each package across all indexes, but prefer \
            the first index with a compatible version, even if newer versions are available \
            on other indexes.

            - ``unsafe-best-match``: Search for each package across all indexes, and select \
            the best version from the combined set of candidate versions (pip's default).
        """
        valid_strategies = ["first-index", "unsafe-first-match", "unsafe-best-match"]
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid index strategy: {strategy}. "
                f"Valid strategies are: {', '.join(valid_strategies)}"
            )

        self.index_strategy = strategy

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
                    logger.warning(
                        "a package '%s' was not found in loadedPackages.", name
                    )

                logger.info("Successfully uninstalled %s-%s", name, version)

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
