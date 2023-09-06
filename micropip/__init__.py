from ._commands.freeze import freeze
from ._commands.index_urls import set_index_urls
from ._commands.install import install
from ._commands.list import _list as list
from ._commands.mock_package import (
    add_mock_package,
    list_mock_packages,
    remove_mock_package,
)
from ._commands.uninstall import uninstall

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
    "set_index_urls",
    "__version__",
]
