import logging
from pathlib import Path
from urllib.parse import urlparse

from pyodide.ffi import create_proxy, to_js
from pyodide.http import pyfetch

from .compatibility_layer import CompatibilityLayer, FetchResponse, LockFile

try:
    import pyodide_js
    from pyodide_js import loadedPackages, loadPackage, lockfileBaseUrl
    from pyodide_js._api import (  # type: ignore[import]
        install,
        loadBinaryFile,
    )
except ImportError as e:
    raise ImportError(
        "Failed to import pyodide modules, please report this issue to Pyodide team."
    ) from e

logger = logging.getLogger("micropip")

# Send pyodide.loadPackage messages to micropip's logger. These proxies are
# never destroyed, since loadPackage may restore them as its default callbacks
# when calls overlap.
_message_callback = create_proxy(logger.info)
_error_callback = create_proxy(logger.warning)


class PyodideCompatibilityLayer(CompatibilityLayer):
    """
    The default compatibility layer, used in the Pyodide runtime.

    Subclass it to change part of the default behavior, e.g. ``fetch``.
    """

    def __init__(self) -> None:
        self.lockfile = LockFile(
            info=pyodide_js._api.lockfile_info.to_py(),
            packages=pyodide_js._api.lockfile_packages.to_py(),
            base_url=lockfileBaseUrl,
        )

    async def fetch(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        credentials: str | None = None,
    ) -> FetchResponse:
        parsed_url = urlparse(url)
        match parsed_url.scheme:
            case "emfs":
                # A path in the Emscripten file system
                return FetchResponse(Path(parsed_url.path).read_bytes())
            case "file":
                # A path in the native file system (Node.js only)
                return FetchResponse((await loadBinaryFile(parsed_url.path)).to_bytes())
            case "http" | "https" | "":
                # An empty scheme is a URL relative to the page
                pass
            case _:
                # Not ValueError: ValueError is treated as "package not found"
                raise TypeError(
                    f"Unexpected URL scheme {parsed_url.scheme!r} in {url!r}. "
                    "Supported schemes are 'https', 'http', 'emfs' and 'file'."
                )

        kwargs: dict[str, object] = {}
        if headers:
            kwargs["headers"] = headers
        if credentials:
            kwargs["credentials"] = credentials

        try:
            response = await pyfetch(url, **kwargs)
            response.raise_for_status()
            content = await response.bytes()
        except OSError as e:
            if not parsed_url.scheme or parsed_url.hostname in (
                "files.pythonhosted.org",
                "cdn.jsdelivr.net",
            ):
                # Relative URLs are same-origin, and these hosts are known to
                # send CORS headers, so CORS is not the problem.
                raise
            raise ValueError(
                f"Can't fetch {url!r}. "
                "One common reason for this is when the server blocks "
                "Cross-Origin Resource Sharing (CORS). "
                "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
            ) from e

        return FetchResponse(content, dict(response.headers))

    async def install(
        self,
        data: bytes,
        filename: str,
        install_dir: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        await install(to_js(data), filename, install_dir, metadata)

    async def load_packages(self, names: list[str]) -> None:
        await loadPackage(
            to_js(names),
            to_js(
                {
                    "messageCallback": _message_callback,
                    "errorCallback": _error_callback,
                }
            ),
        )

    # pyodide.loadedPackages is shared with the JS side (pyodide.loadPackage
    # consults it), so the Pyodide layer keeps it in sync instead of holding
    # its own state.
    def loaded_packages(self) -> dict[str, str]:
        return loadedPackages.to_py()

    def add_loaded_package(self, name: str, source: str) -> None:
        setattr(loadedPackages, name, source)

    def remove_loaded_package(self, name: str) -> bool:
        if not hasattr(loadedPackages, name):
            return False
        delattr(loadedPackages, name)
        return True
