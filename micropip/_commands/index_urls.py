from ..package_index import INDEX_URLS, _check_index_url

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
    
    global INDEX_URLS

    if isinstance(urls, str):
        urls = [urls]

    for url in urls:
        _check_index_url(url)

    INDEX_URLS = urls