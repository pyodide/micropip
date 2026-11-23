from .package_manager import Client

try:
    from ._version import __version__
except ImportError:
    pass

default_client = Client()
"""
The :py:class:`Client` used by the top-level functions.
"""

install = default_client.install
set_index_urls = default_client.set_index_urls
list = default_client.list_packages
set_constraints = default_client.set_constraints
freeze = default_client.freeze
add_mock_package = default_client.add_mock_package
list_mock_packages = default_client.list_mock_packages
remove_mock_package = default_client.remove_mock_package
uninstall = default_client.uninstall

__all__ = [
    "Client",
    "default_client",
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
