from .package_manager import PackageManager

try:
    from ._version import __version__
except ImportError:
    pass

from ._compat import compatibility_layer

_package_manager_singleton = PackageManager(compatibility_layer)

install = _package_manager_singleton.install
set_index_urls = _package_manager_singleton.set_index_urls
list = _package_manager_singleton.list_packages
set_constraints = _package_manager_singleton.set_constraints
freeze = _package_manager_singleton.freeze
add_mock_package = _package_manager_singleton.add_mock_package
list_mock_packages = _package_manager_singleton.list_mock_packages
remove_mock_package = _package_manager_singleton.remove_mock_package
uninstall = _package_manager_singleton.uninstall

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
