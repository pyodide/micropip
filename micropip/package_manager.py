import builtins
from typing import (  # noqa: UP035 List import is necessary due to the `list` method
    Any,
    List,
)

from . import _mock_package, package_index
from ._compat import REPODATA_INFO, REPODATA_PACKAGES
from .freeze import freeze_lockfile
from .install import install
from .list import list_installed_packages
from .package import PackageDict
from .uninstall import uninstall


class PackageManager:
    """
    PackageManager provides an extensible interface for customizing micropip's behavior.

    Each Manager instance holds its own local state that is
    independent of other instances.
    """

    def __init__(self) -> None:
        self.index_urls = package_index.DEFAULT_INDEX_URLS[:]

        self.repodata_packages: dict[str, dict[str, Any]] = REPODATA_PACKAGES
        self.repodata_info: dict[str, str] = REPODATA_INFO

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
        verbose: bool | int | None = None,
    ):
        """Install the given package and all of its dependencies.

        If a package is not found in the Pyodide repository it will be loaded from
        PyPI. Micropip can only load pure Python wheels or wasm32/emscripten wheels
        built by Pyodide.

        When used in web browsers, downloads from PyPI will be cached. When run in
        Node.js, packages are currently not cached, and will be re-downloaded each
        time ``micropip.install`` is run.

        Parameters
        ----------
        requirements :

            A requirement or list of requirements to install. Each requirement is a
            string, which should be either a package name or a wheel URI:

            - If the requirement does not end in ``.whl``, it will be interpreted as
            a package name. A package with this name must either be present
            in the Pyodide lock file or on PyPI.

            - If the requirement ends in ``.whl``, it is a wheel URI. The part of
            the requirement after the last ``/``  must be a valid wheel name in
            compliance with the `PEP 427 naming convention
            <https://www.python.org/dev/peps/pep-0427/#file-format>`_.

            - If a wheel URI starts with ``emfs:``, it will be interpreted as a path
            in the Emscripten file system (Pyodide's file system). E.g.,
            ``emfs:../relative/path/wheel.whl`` or ``emfs:/absolute/path/wheel.whl``.
            In this case, only .whl files are supported.

            - If a wheel URI requirement starts with ``http:`` or ``https:`` it will
            be interpreted as a URL.

            - In node, you can access the native file system using a URI that starts
            with ``file:``. In the browser this will not work.

        keep_going :

            This parameter decides the behavior of the micropip when it encounters a
            Python package without a pure Python wheel while doing dependency
            resolution:

            - If ``False``, an error will be raised on first package with a missing
            wheel.

            - If ``True``, the micropip will keep going after the first error, and
            report a list of errors at the end.

        deps :

            If ``True``, install dependencies specified in METADATA file for each
            package. Otherwise do not install dependencies.

        credentials :

            This parameter specifies the value of ``credentials`` when calling the
            `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__
            function which is used to download the package.

            When not specified, ``fetch()`` is called without ``credentials``.

        pre :

            If ``True``, include pre-release and development versions. By default,
            micropip only finds stable versions.

        index_urls :

            A list of URLs or a single URL to use as the package index when looking
            up packages. If None, *https://pypi.org/pypi/{package_name}/json* is used.

            - The index URL should support the
            `JSON API <https://warehouse.pypa.io/api-reference/json/>`__ .

            - The index URL may contain the placeholder {package_name} which will be
            replaced with the package name when looking up a package. If it does not
            contain the placeholder, the package name will be appended to the URL.

            - If a list of URLs is provided, micropip will try each URL in order until
            it finds a package. If no package is found, an error will be raised.

        verbose :
            Print more information about the process. By default, micropip does not
            change logger level. Setting ``verbose=True`` will print similar
            information as pip.
        """
        if index_urls is None:
            index_urls = self.index_urls

        return await install(
            requirements,
            index_urls,
            keep_going,
            deps,
            credentials,
            pre,
            verbose=verbose,
        )

    def list(self) -> PackageDict:
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
        return list_installed_packages(self.repodata_packages)

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
        return freeze_lockfile(self.repodata_packages, self.repodata_info)

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
        return uninstall(packages, verbose=verbose)

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
