import importlib.metadata
import json
import sys
from copy import deepcopy
from importlib.metadata import Distribution
from typing import TypedDict

from packaging.utils import canonicalize_name
from packaging.version import Version

from .._compat import REPODATA_INFO, REPODATA_PACKAGES
from .._utils import fix_package_dependencies
from ..package_index import query_package

IN_VENV = sys.prefix != sys.base_prefix


class PkgEntry(TypedDict):
    name: str
    version: str
    file_name: str
    install_dir: str
    sha256: str | None
    imports: list[str]
    depends: list[str]


def get_pkg_entry_micropip(dist: Distribution, url: str) -> PkgEntry:
    name = dist.name
    version = dist.version
    sha256 = dist.read_text("PYODIDE_SHA256")
    assert sha256
    imports = (dist.read_text("top_level.txt") or "").split()
    requires = dist.read_text("PYODIDE_REQUIRES")
    if not requires:
        fix_package_dependencies(name)
        requires = dist.read_text("PYODIDE_REQUIRES")
    if requires:
        depends = json.loads(requires)
    else:
        depends = []

    return dict(
        name=name,
        version=version,
        file_name=url,
        install_dir="site",
        sha256=sha256,
        imports=imports,
        depends=depends,
    )


async def get_pkg_entry_pip(dist: Distribution) -> PkgEntry | None:
    resp = await query_package(dist.name)
    ver = resp.releases.get(Version(dist.version), None)
    if ver is None:
        return None
    wheel = next(ver)
    await wheel.download({})
    requires = [req.name for req in wheel.requires(set())]
    return dict(
        name=dist.name,
        version=dist.version,
        file_name=wheel.url,
        install_dir="site",
        sha256=wheel.sha256,
        imports=[],
        depends=requires,
    )


async def freeze2() -> str:
    """Produce a json string which can be used as the contents of the
    ``repodata.json`` lock file.

    If you later load Pyodide with this lock file, you can use
    :js:func:`pyodide.loadPackage` to load packages that were loaded with :py:mod:`micropip`
    this time. Loading packages with :js:func:`~pyodide.loadPackage` is much faster
    and you will always get consistent versions of all your dependencies.

    You can use your custom lock file by passing an appropriate url to the
    ``lockFileURL`` of :js:func:`~globalThis.loadPyodide`.
    """
    packages = deepcopy(REPODATA_PACKAGES)
    for dist in importlib.metadata.distributions():
        name = dist.name
        url = dist.read_text("PYODIDE_URL")
        if url:
            pkg_entry = get_pkg_entry_micropip(dist, url)
        elif IN_VENV:
            res = await get_pkg_entry_pip(dist)
            if not res:
                continue
            pkg_entry = res
        else:
            continue

        packages[canonicalize_name(name)] = pkg_entry

    # Sort
    packages = dict(sorted(packages.items()))
    package_data = {
        "info": REPODATA_INFO,
        "packages": packages,
    }
    return json.dumps(package_data)


def freeze() -> str:
    """Produce a json string which can be used as the contents of the
    ``repodata.json`` lock file.

    If you later load Pyodide with this lock file, you can use
    :js:func:`pyodide.loadPackage` to load packages that were loaded with :py:mod:`micropip`
    this time. Loading packages with :js:func:`~pyodide.loadPackage` is much faster
    and you will always get consistent versions of all your dependencies.

    You can use your custom lock file by passing an appropriate url to the
    ``lockFileURL`` of :js:func:`~globalThis.loadPyodide`.
    """
    packages = deepcopy(REPODATA_PACKAGES)
    for dist in importlib.metadata.distributions():
        name = dist.name
        url = dist.read_text("PYODIDE_URL")
        if url is None:
            continue
        pkg_entry = get_pkg_entry_micropip(dist, url)
        packages[canonicalize_name(name)] = pkg_entry

    # Sort
    packages = dict(sorted(packages.items()))
    package_data = {
        "info": REPODATA_INFO,
        "packages": packages,
    }
    return json.dumps(package_data)
