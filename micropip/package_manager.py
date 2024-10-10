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
        return list_installed_packages(self.repodata_packages)

    def freeze(self) -> str:
        return freeze_lockfile(self.repodata_packages, self.repodata_info)

    def add_mock_package(
        self,
        name: str,
        version: str,
        *,
        modules: dict[str, str | None] | None = None,
        persistent: bool = False,
    ):
        return _mock_package.add_mock_package(
            name, version, modules=modules, persistent=persistent
        )

    def list_mock_packages(self):
        return _mock_package.list_mock_packages()

    def remove_mock_package(self, name: str):
        return _mock_package.remove_mock_package(name)

    def uninstall(self):
        raise NotImplementedError()

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
