import importlib.metadata
import json

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from .._compat import REPODATA_INFO, REPODATA_PACKAGES


def check_package_dependencies(
    package_name, *, extras=None, fix_deps=False, recursive=True
):
    """Check and optionally fix the list of dependencies for this package

    If you have manually installed a package and dependencies from wheels,
    the dependencies will not be correctly setup in the package list
    or the pyodide lockfile generated by freezing. This method checks
    if the dependencies are correctly set in the package list, and if
    fix_deps is True, it will add missing dependencies.

    Parameters
    ----------
    package_name (string):
        The name of the package to check.

    extras (list):
        List of extras for this package.

    fix_deps (boolean):
        If this is True, any missing dependencies that are in
        the current package list will be added to the current 
        package. 

    recursive (boolean):
        If this is True, dependencies of dependencies will be checked.
    
    Returns
    -------
    dict: 
        Dictionary mapping package name to a list of missing dependencies. 
        If the package has no missing dependencies, an empty list is returned.
    """
    if package_name in REPODATA_PACKAGES:
        # don't check things that are in original repository
        return {}

    dist = importlib.metadata.Distribution.from_name(package_name)
    url = dist.read_text("PYODIDE_URL")

    # If it wasn't installed with micropip / pyodide, then we
    # can't do anything with it.
    assert url is not None

    # Get current list of pyodide requirements
    requires = dist.read_text("PYODIDE_REQUIRES")

    if requires:
        depends = json.loads(requires)
    else:
        depends = []

    missing = []
    all_missing = {}

    package_requires = dist.requires
    if package_requires == None:
        # no dependencies - we're good to go
        return {}

    if extras == None:
        extras = [None]
    else:
        extras = extras.append(None)
    for r in package_requires:
        req = Requirement(r)
        req_extras = req.extras
        req_marker = req.marker
        req_name = canonicalize_name(req.name)
        needs_requirement = False
        if req_marker != None:
            for e in extras:
                if req_marker.evaluate(None if e == None else {"extra": e}):
                    needs_requirement = True
                    break
        else:
            needs_requirement = True

        if needs_requirement:
            if recursive:
                all_missing = all_missing | check_package_dependencies(
                    req_name, extras=list(req_extras), fix_deps=fix_deps
                )

            if not req_name in depends:
                missing.append(req_name)
                depends.append(req_name)

    if fix_deps and len(missing) > 0:
        # write updated depends to PYODIDE_DEPENDS
        (dist._path / "PYODIDE_REQUIRES").write_text(
            json.dumps(sorted(x for x in depends))
        )
    if len(missing) > 0:
        all_missing[package_name] = missing
    return all_missing
