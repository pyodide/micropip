"""
Compatibility layers connect micropip to the runtime it runs in.

Pass an instance of a :py:class:`CompatibilityLayer` subclass to
:py:class:`micropip.Client` to change how micropip fetches files, installs
wheels, or reads the lock file. :py:class:`PyodideCompatibilityLayer` is the
default layer, and can only be imported in Pyodide.
"""

from typing import Any

from ._compat import (
    _IN_PYODIDE,
    CompatibilityLayer,
    FetchOptions,
    FetchResponse,
    LockedPackage,
    LockFile,
)

# PyodideCompatibilityLayer is not in __all__ so that
# ``from micropip.compat import *`` works outside of Pyodide.
__all__ = [
    "CompatibilityLayer",
    "FetchOptions",
    "FetchResponse",
    "LockFile",
    "LockedPackage",
]


def __getattr__(name: str) -> Any:
    # Imported lazily so that ``import micropip.compat`` works outside of Pyodide.
    if name == "PyodideCompatibilityLayer":
        if not _IN_PYODIDE:
            raise ImportError(
                "PyodideCompatibilityLayer is only available in the Pyodide runtime."
            )
        from ._compat._compat_in_pyodide import PyodideCompatibilityLayer

        return PyodideCompatibilityLayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
