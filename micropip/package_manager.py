import builtins
import importlib
import importlib.metadata
from importlib.metadata import Distribution
from pathlib import Path
from typing import (  # noqa: UP035 List import is necessary due to the `list` method
    List,
)

from . import _mock_package, package_index
from ._compat import CompatibilityLayer, FetchOptions, get_default_compatibility_layer
from ._vendored.packaging.src.packaging.markers import default_environment
from .constants import FAQ_URLS
from .installer import Installer
from .logging import indent_log, setup_logging
from .package import PackageDict, PackageMetadata
from .resolver import Resolver
from .sources import Source


class Client:
    """
    A micropip client, with its own index URLs, constraints and compatibility layer.

    The module-level functions (``micropip.install``, ``micropip.list``, ...) use a
    default client. Create a ``Client`` to use different settings, e.g. a custom
    compatibility layer:

    .. code-block:: python

        import micropip
        from micropip.compat import PyodideCompatibilityLayer

        class CachedCompatibilityLayer(PyodideCompatibilityLayer):
            async def fetch(self, url, options):
                if url not in cache:
                    cache[url] = await super().fetch(url, options)
                return cache[url]

        client = micropip.Client(compat=CachedCompatibilityLayer())
        await client.install("snowballstemmer")

    Each client holds its own local state that is independent of other clients.

    Subclasses can replace how packages are resolved and installed by
    overriding ``resolver_class`` and ``installer_class``.
    """

    resolver_class: type[Resolver] = Resolver
    """The class used to find and download the packages to install."""

    installer_class: type[Installer] = Installer
    """The class used to install and uninstall packages."""

    def __init__(self, compat: CompatibilityLayer | None = None) -> None:
        """
        Parameters
        ----------
        compat
            The :py:class:`~micropip.compat.CompatibilityLayer` that connects
            micropip to the runtime (fetching files, installing wheels, the lock
            file, ...). Defaults to the Pyodide compatibility layer.
        """
        self.index_urls: builtins.list[str | Source] = list[str | Source](
            package_index.DEFAULT_INDEX_URLS
        )
        self._compat_layer = compat
        self.constraints: list[str] = []

    @property
    def compat_layer(self) -> CompatibilityLayer:
        # Resolved on first use, so a Client can be created outside of
        # Pyodide (e.g. the module-level singleton on ``import micropip``).
        if self._compat_layer is None:
            self._compat_layer = get_default_compatibility_layer()
        return self._compat_layer

    def _installer(self) -> Installer:
        return self.installer_class(self.compat_layer)

    async def install(
        self,
        requirements: str | list[str],
        keep_going: bool = False,
        deps: bool = True,
        credentials: str | None = None,
        pre: bool = False,
        index_urls: "builtins.list[str | Source] | str | None" = None,
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
            up packages. If None, the index URLs set with :py:meth:`set_index_urls`
            are used (by default, *https://pypi.org/simple*).

            - The index URL should support the \
            `Simple repository API <https://packaging.python.org/en/latest/specifications/simple-repository-api/>`__ .

            - If a list of URLs is provided, micropip will try each URL in order until \
            it finds a package. If no package is found, an error will be raised.

            - The index URL must support CORS when used in a web browser.

            - The special value ``"PYPI"`` is replaced with *https://pypi.org/simple*.

            - The special value ``"PYODIDE"`` stands for the Pyodide lock file: \
            micropip looks for the package in the lock file at that position, \
            and moves on to the next index if the lock file does not have a \
            version that satisfies the requirement. For example, \
            ``["PYODIDE", "https://example.com/simple", "PYPI"]`` searches the \
            lock file, then *example.com*, then PyPI.

            - If ``"PYODIDE"`` is not in the list, the lock file is searched first \
            when the index URLs are left at the default, and after the given \
            index URLs otherwise.

            - Entries can also be :py:class:`micropip.sources.Source` objects, \
            to look up packages somewhere other than a package index.

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

        Examples
        --------
        >>> import micropip
        >>> await micropip.install("snowballstemmer")
        >>> await micropip.install(["snowballstemmer", "mccabe"])
        >>> await micropip.install("numpy>=2.2.0")
        """

        with setup_logging().ctx_level(verbose) as logger:
            if index_urls is None:
                index_urls = self.index_urls

            if constraints is None:
                constraints = self.constraints

            ctx = default_environment()
            if isinstance(requirements, str):
                requirements = [requirements]

            # Note: getsitepackages is not available in a virtual environment...
            # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
            # problem is not fixed)
            from site import getsitepackages

            wheel_base = Path(getsitepackages()[0])

            resolver = self.resolver_class(
                compat_layer=self.compat_layer,
                ctx=ctx,  # type: ignore[arg-type]
                ctx_extras=[],
                keep_going=keep_going,
                deps=deps,
                pre=pre,
                fetch_options=FetchOptions(credentials=credentials),
                verbose=verbose,
                index_urls=index_urls,
                constraints=constraints,
                reinstall=reinstall,
            )
            await resolver.gather_requirements(requirements)

            if resolver.failed:
                failed_requirements = ", ".join([f"'{req}'" for req in resolver.failed])
                raise ValueError(
                    f"Can't find a pure Python 3 wheel for: {failed_requirements}\n"
                    f"See: {FAQ_URLS['cant_find_wheel']}\n"
                )

            pyodide_packages, wheels = resolver.pyodide_packages, resolver.wheels

            packages_all = [pkg.name for pkg in wheels + pyodide_packages]

            distributions = search_installed_packages(packages_all)
            # This check is redundant because the distributions will always be an empty list when reinstall==False
            # (no installed packages will be returned from the resolver)
            # But just in case.
            installer = self._installer()
            if reinstall:
                with indent_log():
                    installer.uninstall(distributions)

            logger.debug(
                "Installing packages %r and wheels %r ",
                resolver.pyodide_packages,
                [w.filename for w in resolver.wheels],
            )

            if packages_all:
                logger.info(
                    "Installing collected packages: %s", ", ".join(packages_all)
                )

            await installer.install(wheels, pyodide_packages, wheel_base)

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

        lockfile = self.compat_layer.lockfile
        for name, pkg_source in self.compat_layer.loaded_packages().items():
            if name in packages:
                continue

            locked_package = lockfile.get(name) if lockfile is not None else None
            if locked_package is not None:
                version = locked_package.version
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

        The output format is that of the compatibility layer's
        :py:class:`~micropip.compat.LockFile`. Raises ``RuntimeError`` if the
        compatibility layer has no lock file.
        """
        lockfile = self.compat_layer.lockfile
        if lockfile is None:
            raise RuntimeError(
                "micropip.freeze() needs a lock file, but the compatibility layer "
                "does not provide one."
            )
        return lockfile.freeze()

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

            self._installer().uninstall(distributions)

            importlib.invalidate_caches()

    def set_index_urls(self, urls: "List[str | Source] | str"):  # noqa: UP006
        """
        Set the index URLs to use when looking up packages.

        - The index URL should support the
            `Simple repository API <https://packaging.python.org/en/latest/specifications/simple-repository-api/>`__ .

        - The index URL may contain the placeholder {package_name} which will be
            replaced with the package name when looking up a package. If it does not
            contain the placeholder, the package name will be appended to the URL.

        - If a list of URLs is provided, micropip will try each URL in order until
            it finds a package. If no package is found, an error will be raised.

        - The index URL must support CORS when used in a web browser.

        - The special value ``"PYPI"`` is replaced with https://pypi.org/simple.

        - The special value ``"PYODIDE"`` stands for the Pyodide lock file:
            micropip looks for the package in the lock file at that position, and
            moves on to the next index if the lock file does not have a version
            that satisfies the requirement.

        - If ``"PYODIDE"`` is not in the list, the lock file is searched first when
            the index URLs are left at the default, and after the given index URLs
            otherwise.

        - Entries can also be :py:class:`micropip.sources.Source` objects, to look
            up packages somewhere other than a package index.

        Parameters
        ----------
        urls
            A list of URLs (or sources), or a single URL, to use as the package index.

        Examples
        --------
        Prefer the packages that come with Pyodide, then a custom index, then PyPI:

        .. code-block:: python

            micropip.set_index_urls(["PYODIDE", "https://example.com/simple", "PYPI"])
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


# The name used before Client was made public.
PackageManager = Client


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
