from ._micropip import _list as list
from ._micropip import add_mock_package, freeze, install

try:
    from ._version import __version__
except ImportError:
    pass

__all__ = ["install", "list", "freeze", "add_mock_package", "__version__"]
