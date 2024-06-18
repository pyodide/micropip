from typing import Any, List

from micropip import package_index


class Manager:
    """
    Manager provides an extensible interface for customizing micropip's behavior.

    Each Manager instance holds its own local state that is
    independent of other instances, including the global state.

    TODO: Implement all of the following global commands to utilize local state.
    """

    def __init__(self):
        self.index_urls = package_index.DEFAULT_INDEX_URLS

        # TODO: initialize the compatibility layer
        self.repodata_packages: dict[str, dict[str, Any]] = {}
        self.repodata_info: dict[str, str] = {}

        pass

    def install(self):
        raise NotImplementedError()

    def list(self):
        raise NotImplementedError()

    def freeze(self):
        raise NotImplementedError()

    def add_mock_package(self):
        raise NotImplementedError()

    def list_mock_packages(self):
        raise NotImplementedError()

    def remove_mock_package(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()

    def set_index_urls(self, urls: List[str] | str):
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
