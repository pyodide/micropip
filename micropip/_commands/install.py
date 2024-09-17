from micropip import package_index

from ..install import install as _install


async def install(
    requirements: str | list[str],
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
    index_urls: list[str] | str | None = None,
    *,
    verbose: bool | int | None = None,
) -> None:
    if index_urls is None:
        index_urls = package_index.INDEX_URLS[:]

    return await _install(
        requirements, keep_going, deps, credentials, pre, index_urls, verbose=verbose
    )
