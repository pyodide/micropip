import sys
from functools import cache

from .compatibility_layer import CompatibilityLayer

_IN_PYODIDE = "_pyodide_core" in sys.modules


@cache
def get_default_compatibility_layer() -> CompatibilityLayer:
    """
    Return the compatibility layer for the current runtime.

    micropip only ships a compatibility layer for Pyodide. Outside of Pyodide,
    ``import micropip`` still works (e.g. to build docs or run unit tests), but
    anything that needs the runtime raises an error unless a layer is passed to
    ``PackageManager`` explicitly.
    """
    if not _IN_PYODIDE:
        raise RuntimeError(
            "micropip requires the Pyodide runtime, but it is not running in Pyodide."
        )

    from ._compat_in_pyodide import CompatibilityInPyodide

    return CompatibilityInPyodide()


__all__ = [
    "CompatibilityLayer",
    "get_default_compatibility_layer",
]
