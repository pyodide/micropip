from .freeze import freeze
from .install import install
from .list import _list as list
from .mock_package import (
    add_mock_package,
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
