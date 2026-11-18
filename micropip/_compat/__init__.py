import sys

from .compatibility_layer import CompatibilityLayer

compatibility_layer: type[CompatibilityLayer]

_IN_PYODIDE = "_pyodide_core" in sys.modules

if _IN_PYODIDE:
    from ._compat_in_pyodide import CompatibilityInPyodide

    compatibility_layer = CompatibilityInPyodide
else:
    from ._compat_not_in_pyodide import CompatibilityNotInPyodide

    compatibility_layer = CompatibilityNotInPyodide

__all__ = [
    "CompatibilityLayer",
    "compatibility_layer",
]
