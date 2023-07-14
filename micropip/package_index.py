import json
from typing import Any

from ._compat import fetch_string

DEFAULT_INDEX_URLS = ["https://pypi.org/pypi/{package_name}/json"]
INDEX_URLS = DEFAULT_INDEX_URLS

def _check_index_url(url: str) -> None:
    try:
        url.format(package_name=".")
    except KeyError:
        raise ValueError(
            f"Invalid index URL: {url!r}. "
            "Please make sure it contains the placeholder {package_name}."
        )


async def search_packages(pkgname: str, fetch_kwargs: dict[str, str], index_urls: list[str] | str | None = None) -> Any:
    global INDEX_URLS

    if index_urls is None:
        index_urls = INDEX_URLS
    elif isinstance(index_urls, str):
        index_urls = [index_urls]
    
    for url in index_urls:
        _check_index_url(url)

        url = url.format(package_name=pkgname)

        try:
            metadata = await fetch_string(url, fetch_kwargs)
        except OSError:
            continue

        return json.loads(metadata)
    else:
        raise ValueError(
            f"Can't fetch metadata for '{pkgname}' from PyPI. "
            "Please make sure you have entered a correct package name."
        )