from .commands.freeze import freeze
from .commands.install import install
from .commands.list import _list as list
from .commands.mock_package import (
    add_mock_package,
    list_mock_packages,
    remove_mock_package,
)
from .commands.uninstall import uninstall

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
