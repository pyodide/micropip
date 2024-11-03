import importlib.metadata
from typing import Any

from ._compat import loadedPackages
from .package import PackageDict, PackageMetadata


def list_installed_packages(
    lockfile_packages: dict[str, dict[str, Any]]
) -> PackageDict:
    # Add packages that are loaded through pyodide.loadPackage
    packages = PackageDict()
    for dist in importlib.metadata.distributions():
        name = dist.name
        version = dist.version
        source = dist.read_text("PYODIDE_SOURCE")
        if source is None:
            # source is None if PYODIDE_SOURCE does not exist. In this case the
            # wheel was installed manually, not via `pyodide.loadPackage` or
            # `micropip`.
            continue
        packages[name] = PackageMetadata(
            name=name,
            version=version,
            source=source,
        )

    for name, pkg_source in loadedPackages.to_py().items():
        if name in packages:
            continue

        if name in lockfile_packages:
            version = lockfile_packages[name]["version"]
            source_ = "pyodide"
            if pkg_source != "default channel":
                # Pyodide package loaded from a custom URL
                source_ = pkg_source
        else:
            # TODO: calculate version from wheel metadata
            version = "unknown"
            source_ = pkg_source
        packages[name] = PackageMetadata(name=name, version=version, source=source_)
    return packages
