from .. import package_index


def set_index_urls(urls: list[str] | str) -> None:
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

    package_index.INDEX_URLS = urls[:]
