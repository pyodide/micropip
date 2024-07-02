from micropip.list import list_installed_packages

from .._compat import REPODATA_PACKAGES
from ..package import PackageDict


def _list() -> PackageDict:
    return list_installed_packages(REPODATA_PACKAGES)
