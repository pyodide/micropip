import importlib.metadata
import itertools
import json
from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from packaging.utils import canonicalize_name

from .._compat import REPODATA_INFO, REPODATA_PACKAGES
from .._utils import fix_package_dependencies


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
    return json.dumps(freeze_data())


def freeze_data() -> dict[str, Any]:
    pyodide_packages = deepcopy(REPODATA_PACKAGES)
    pip_packages = load_pip_packages()
    package_items = itertools.chain(pyodide_packages.items(), pip_packages)

    # Sort
    packages = dict(sorted(package_items))
    return {
        "info": REPODATA_INFO,
        "packages": packages,
    }


def load_pip_packages() -> Iterator[tuple[str, dict[str, Any]]]:
    return map(
        package_item,
        filter(is_valid, map(load_pip_package, importlib.metadata.distributions())),
    )


def package_item(entry: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return canonicalize_name(entry["name"]), entry


def is_valid(entry: dict[str, Any]) -> bool:
    return entry["file_name"] is not None


def load_pip_package(dist: importlib.metadata.Distribution) -> dict[str, Any]:
    name = dist.name
    version = dist.version
    url = dist.read_text("PYODIDE_URL")
    sha256 = dist.read_text("PYODIDE_SHA256")
    imports = (dist.read_text("top_level.txt") or "").split()
    requires = dist.read_text("PYODIDE_REQUIRES")
    if not requires:
        fix_package_dependencies(name)
        requires = dist.read_text("PYODIDE_REQUIRES")
    depends = json.loads(requires or "[]")

    return dict(
        name=name,
        version=version,
        file_name=url,
        install_dir="site",
        sha256=sha256,
        imports=imports,
        depends=depends,
    )
