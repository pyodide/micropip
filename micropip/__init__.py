from ._micropip import _list as list
from ._micropip import freeze, install

try:
    from ._version import __version__
except ImportError:
    pass

__all__ = ["install", "list", "freeze", "__version__"]
