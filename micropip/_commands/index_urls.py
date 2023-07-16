from .. import package_index


def set_index_urls(urls: list[str] | str) -> None:
    """
    Set the index URLs to use when looking up packages.

    The URLs should contain the placeholder {package_name} which will be
    replaced with the package name when looking up a package.

    Parameters
    ----------
    urls
        A list of URLs or a single URL to use as the package index.
    """

    if isinstance(urls, str):
        urls = [urls]

    for url in urls:
        package_index._check_index_url(url)

    package_index.INDEX_URLS = urls
