from ._micropip import _list as list
from ._micropip import freeze, install

__all__ = ["install", "list", "freeze"]

try:
    from ._version import __version__
except ImportError:
    pass
