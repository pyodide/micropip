from .package_manager import Client

try:
    from ._version import __version__
except ImportError:
    pass

default_client = Client()
"""
The :py:class:`Client` used by the module-level functions (``micropip.install``,
``micropip.set_index_urls``, ...). Use it to share their settings, e.g. to
change ``default_client.index_urls`` or swap its ``resolver_class``.
"""

# The private name used before default_client was public. Some downstream code
# still imports it (e.g. to change index_urls), so keep it as an alias.
_package_manager_singleton = default_client

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
