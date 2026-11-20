import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pyodide.ffi import create_proxy, to_js
from pyodide.http import pyfetch

from .._vendored.packaging.src.packaging.utils import canonicalize_name
from ._pyodide_lock import freeze_lockfile
from .compatibility_layer import (
    CompatibilityLayer,
    FetchOptions,
    FetchResponse,
    LockedPackage,
    LockFile,
)

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


class PyodideLockFile(LockFile):
    """
    The ``pyodide-lock.json`` that Pyodide was loaded with.

    Packages are loaded with ``pyodide.loadPackage``.
    """

    def __init__(self) -> None:
        self.info: dict[str, Any] = pyodide_js._api.lockfile_info.to_py()
        self.packages: dict[str, dict[str, Any]] = (
            pyodide_js._api.lockfile_packages.to_py()
        )
        self.base_url: str | None = lockfileBaseUrl

    def get(self, name: str) -> LockedPackage | None:
        package = self.packages.get(name)
        if package is None:
            return None
        return LockedPackage(
            name=name,
            version=str(package["version"]),
            depends=list(package.get("depends", [])),
        )

    async def load(self, names: list[str]) -> list[str]:
        # What is loaded is decided by checking pyodide.loadedPackages after
        # the call, so this works whichever way loadPackage reports failures:
        # - Pyodide currently doesn't raise when a package fails to load (it
        #   only calls errorCallback), and
        # - its return value only lists packages loaded by this call, not the
        #   ones that were already loaded.
        # If a later Pyodide raises instead, the error is logged and the
        # packages that did load are still reported as loaded.
        error: Exception | None = None
        try:
            await loadPackage(
                to_js(names),
                to_js(
                    {
                        "messageCallback": _message_callback,
                        "errorCallback": _error_callback,
                    }
                ),
            )
        except Exception as e:
            error = e

        loaded_names = {canonicalize_name(name) for name in loadedPackages.to_py()}
        loaded = [name for name in names if canonicalize_name(name) in loaded_names]

        if error is not None:
            if len(loaded) == len(names):
                # Every requested package is loaded, so the error is about
                # something else (e.g. a dependency): don't hide it.
                raise error
            logger.warning("Error while loading packages from the lock file: %s", error)

        return loaded

    def freeze(self) -> str:
        return freeze_lockfile(self.packages, self.info, self.base_url)


class PyodideCompatibilityLayer(CompatibilityLayer):
    """
    The default compatibility layer, used in the Pyodide runtime.

    Subclass it to change part of the default behavior, e.g. ``fetch``.
    """

    def __init__(self) -> None:
        self.lockfile: LockFile | None = PyodideLockFile()

    async def fetch(self, url: str, options: FetchOptions) -> FetchResponse:
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

        kwargs: dict[str, Any] = dict(options.extra)
        if options.headers:
            kwargs["headers"] = options.headers
        if options.credentials:
            kwargs["credentials"] = options.credentials

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
