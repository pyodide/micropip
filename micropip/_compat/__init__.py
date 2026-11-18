import sys

from .compatibility_layer import CompatibilityLayer

_IN_PYODIDE = "_pyodide_core" in sys.modules

_default_compatibility_layer: type[CompatibilityLayer] | None = None

if _IN_PYODIDE:
    from ._compat_in_pyodide import CompatibilityInPyodide

    _default_compatibility_layer = CompatibilityInPyodide


def get_default_compatibility_layer() -> type[CompatibilityLayer]:
    """
    Return the compatibility layer for the current runtime.

    micropip only ships a compatibility layer for Pyodide. Outside of Pyodide,
    ``import micropip`` still works (e.g. to build docs or run unit tests), but
    anything that needs the runtime raises an error unless a layer is passed to
    ``PackageManager`` explicitly.
    """
    if _default_compatibility_layer is None:
        raise RuntimeError(
            "micropip requires the Pyodide runtime, but it is not running in Pyodide."
        )
    return _default_compatibility_layer


__all__ = [
    "CompatibilityLayer",
    "get_default_compatibility_layer",
]
