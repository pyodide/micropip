from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Concatenate, ParamSpec, TypeVar
from urllib.parse import urlparse

from pyodide._package_loader import get_dynlibs
from pyodide.ffi import IN_BROWSER, to_js
from pyodide.http import pyfetch

try:
    import pyodide_js
    from js import AbortController, AbortSignal, Object
    from pyodide_js import loadedPackages, loadPackage
    from pyodide_js._api import (  # type: ignore[import]
        loadBinaryFile,
        loadDynlibsFromPackage,
    )

    REPODATA_PACKAGES = pyodide_js._api.repodata_packages.to_py()
    REPODATA_INFO = pyodide_js._api.repodata_info.to_py()
except ImportError:
    if IN_BROWSER:
        raise
    # Otherwise, this is pytest test collection so let it go.

if IN_BROWSER or TYPE_CHECKING:
    P = ParamSpec("P")
    T = TypeVar("T")

    def _abort_on_cancel(
        func: Callable[Concatenate[AbortSignal, P], Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        """inject an AbortSignal as the first argument"""

        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            controller = AbortController.new()
            try:
                return await func(controller.signal, *args, **kwargs)
            except CancelledError:
                controller.abort()
                raise

        return wrapper

else:
    _abort_on_cancel = lambda func: lambda *args, **kwargs: func(None, *args, **kwargs)


@_abort_on_cancel
async def fetch_bytes(signal: AbortSignal, url: str, kwargs: dict[str, str]) -> bytes:
    parsed_url = urlparse(url)
    if parsed_url.scheme == "emfs":
        return Path(parsed_url.path).read_bytes()
    if parsed_url.scheme == "file":
        return (await loadBinaryFile(parsed_url.path)).to_bytes()

    return await (await pyfetch(url, **kwargs, signal=signal)).bytes()


@_abort_on_cancel
async def fetch_string_and_headers(
    signal: AbortSignal, url: str, kwargs: dict[str, str]
) -> tuple[str, dict[str, str]]:
    response = await pyfetch(url, **kwargs, signal=signal)

    content = await response.string()
    # TODO: replace with response.headers when pyodide>= 0.24 is released
    headers: dict[str, str] = Object.fromEntries(
        response.js_response.headers.entries()
    ).to_py()

    return content, headers


__all__ = [
    "fetch_bytes",
    "fetch_string_and_headers",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadDynlibsFromPackage",
    "loadPackage",
    "get_dynlibs",
    "to_js",
]
