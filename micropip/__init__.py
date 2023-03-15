from ._micropip import _list as list
from ._micropip import (
    add_mock_package,
    freeze,
    install,
    list_mock_packages,
    remove_mock_package,
)
from .uninstall import uninstall

try:
    from ._version import __version__
except ImportError:
    pass

__all__ = [
    "install",
    "list",
    "freeze",
    "add_mock_package",
    "list_mock_packages",
    "remove_mock_package",
    "uninstall",
    "__version__",
]
