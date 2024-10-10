from ._commands.uninstall import uninstall

from .package_manager import PackageManager

try:
    from ._version import __version__
except ImportError:
    pass

singleton_package_manager = PackageManager()

install = singleton_package_manager.install
set_index_urls = singleton_package_manager.set_index_urls
list = singleton_package_manager.list
freeze = singleton_package_manager.freeze
add_mock_package = singleton_package_manager.add_mock_package
list_mock_packages = singleton_package_manager.list_mock_packages
remove_mock_package = singleton_package_manager.remove_mock_package

# TODO: port uninstall
# uninstall = singleton_package_manager.uninstall

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
