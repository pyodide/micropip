import hashlib
import json
from urllib.parse import urljoin, urlparse

import pytest
from pytest_pyodide import run_in_pyodide

from micropip._vendored.packaging.src.packaging.utils import (
    canonicalize_name,
    parse_wheel_filename,
)
from micropip._vendored.packaging.src.packaging.version import Version

FREEZE_TOPLEVEL = {
    "dummy": ["abc", "def", "geh"],
    "dep1": ["c", "h", "i"],
    "dep2": ["a12", "b13"],
}


def _add_freeze_packages(fake_index):
    fake_index.add_pkg_version(
        "dummy", requirements=["dep1", "dep2"], top_level=FREEZE_TOPLEVEL["dummy"]
    )
    fake_index.add_pkg_version("dep1", top_level=FREEZE_TOPLEVEL["dep1"])
    fake_index.add_pkg_version("dep2", top_level=FREEZE_TOPLEVEL["dep2"])


@pytest.mark.parametrize("deps", [True, False])
def test_freeze(selenium_standalone_micropip, fake_index, deps):
    """
    freeze() should record dependencies and top-level imports of installed packages.
    When installed with deps=False, dependencies should still be recorded
    once all of them are installed.
    """
    _add_freeze_packages(fake_index)

    @run_in_pyodide
    async def run(selenium, index_url, deps, toplevel):
        import json

        import micropip

        if deps:
            await micropip.install("dummy", index_urls=[index_url])
        else:
            for pkg in ("dummy", "dep1", "dep2"):
                await micropip.install(pkg, index_urls=[index_url], deps=False)

        lockfile = json.loads(micropip.freeze())

        packages = lockfile["packages"]
        assert packages["dummy"]["depends"] == ["dep1", "dep2"]
        assert packages["dep1"]["depends"] == []
        assert packages["dep2"]["depends"] == []
        for name, imports in toplevel.items():
            assert packages[name]["imports"] == imports

    run(selenium_standalone_micropip, fake_index.url, deps, FREEZE_TOPLEVEL)


@pytest.mark.parametrize(
    ("name", "depends"),
    [
        ["pytest", {"attrs", "iniconfig", "packaging", "pluggy"}],
        ["snowballstemmer", set()],
    ],
)
def test_freeze_lockfile_compat(
    name, depends, selenium_standalone_micropip, wheel_catalog, tmp_path
):
    from pyodide_lock import PyodideLockSpec

    selenium = selenium_standalone_micropip
    wheel = wheel_catalog.get(name)
    url = wheel.url

    lockfile_content = selenium.run_async(f"""
        await micropip.install("{url}")
        micropip.freeze()
    """)

    lockfile_path = tmp_path / "lockfile.json"
    with open(lockfile_path, "w") as f:
        f.write(lockfile_content)

    lockfile = PyodideLockSpec.from_json(lockfile_path)
    package = lockfile.packages[name]
    assert package.file_name == url
    assert package.name == name
    assert set(package.depends) == depends
    assert name in package.imports
    assert package.install_dir == "site"
    assert not package.unvendored_tests
    assert package.version == wheel.version


def test_override_base_url():
    from micropip.freeze import override_base_url

    lockfile_packages = {
        "pkg1": {"file_name": "pkg1-1.0.0-py3-none-any.whl"},
        "pkg2": {"file_name": "pkg2-2.0.0-py3-none-any.whl"},
        "pkg3": {"file_name": "https://other.com/pkg3-3.0.0-py3-none-any.whl"},
    }
    base_url = "https://example.com/packages/"

    override_base_url(lockfile_packages, base_url)

    assert (
        lockfile_packages["pkg1"]["file_name"]
        == "https://example.com/packages/pkg1-1.0.0-py3-none-any.whl"
    )
    assert (
        lockfile_packages["pkg2"]["file_name"]
        == "https://example.com/packages/pkg2-2.0.0-py3-none-any.whl"
    )
    assert (
        lockfile_packages["pkg3"]["file_name"]
        == "https://other.com/pkg3-3.0.0-py3-none-any.whl"
    )


def test_url_after_freeze_pyodide(selenium_standalone_micropip):

    @run_in_pyodide
    def _run(selenium, prefix):
        import json

        from pyodide_js import lockfileBaseUrl
        from pyodide_js._api import lockfile_packages

        import micropip

        new_lockfile_str = micropip.freeze()
        new_lockfile_packages = json.loads(new_lockfile_str)["packages"]

        orig_lockfile_packages = lockfile_packages.to_py()

        for orig_pkg_name, orig_pkg in orig_lockfile_packages.items():
            assert orig_pkg_name in new_lockfile_packages

            new_pkg = new_lockfile_packages[orig_pkg_name]

            assert new_pkg["name"] == orig_pkg["name"]
            assert new_pkg["version"] == orig_pkg["version"]
            assert new_pkg["sha256"] == orig_pkg["sha256"]
            assert new_pkg["imports"] == orig_pkg["imports"]
            assert new_pkg["depends"] == orig_pkg["depends"]
            assert new_pkg["install_dir"] == orig_pkg["install_dir"]
            assert new_pkg["unvendored_tests"] == orig_pkg["unvendored_tests"]

            # original lockfile will have relative URLs
            # TODO: this might change later if packages are served from PyPI
            assert not orig_pkg["file_name"].startswith(prefix)

            # new lockfile should have absolute URLs
            assert new_pkg["file_name"].startswith(prefix)
            assert new_pkg["file_name"].startswith(lockfileBaseUrl)

            assert orig_pkg["file_name"] in new_pkg["file_name"]

    selenium = selenium_standalone_micropip
    prefix = ("/",) if selenium.browser == "node" else ("http://", "https://")
    _run(selenium, prefix)


# ---------------------------------------------------------------------------
# Validate micropip.freeze() output against the pyodide-lock spec.
#
# The output of micropip.freeze() is meant to be used as a pyodide-lock.json
# (e.g. by pyodide-pack), so the tests below parse it on the host with
# pyodide_lock.PyodideLockSpec and check that the result is a consistent
# lockfile. See https://github.com/pyodide/micropip/issues/88
# ---------------------------------------------------------------------------


@run_in_pyodide
async def _install_and_freeze(selenium, requirements, index_url, deps=True):
    """
    Install ``requirements`` with micropip, then return the frozen lockfile
    together with the lockfile Pyodide was loaded with.
    """
    import json

    from pyodide_js import lockfileBaseUrl
    from pyodide_js._api import lockfile_info, lockfile_packages

    import micropip

    for req in requirements:
        await micropip.install(req, index_urls=[index_url], deps=deps)

    return {
        "frozen": micropip.freeze(),
        "orig_info": json.dumps(lockfile_info.to_py()),
        "orig_packages": json.dumps(lockfile_packages.to_py()),
        "base_url": lockfileBaseUrl,
    }


def _parse_lockfile(frozen: str, check_depends: bool = True):
    """Parse the output of micropip.freeze() with pyodide-lock."""
    from pyodide_lock import PyodideLockSpec

    data = json.loads(frozen)

    # pyodide-lock coerces values (e.g. None -> "None" for str fields),
    # so make sure freeze() does not emit nulls in the first place.
    for name, pkg in data["packages"].items():
        nulls = [key for key, value in pkg.items() if value is None]
        assert not nulls, f"{name} has null fields: {nulls}"

    lockfile = PyodideLockSpec.from_dict(data)

    for key, pkg in lockfile.packages.items():
        assert key == canonicalize_name(pkg.name)

        # Names and versions in wheel file names must match the package entry.
        # (PyodideLockSpec.check_wheel_filenames() can't be used here as it
        # does not support URLs, and freeze() makes all file names absolute.)
        wheel_filename = urlparse(pkg.file_name).path.rsplit("/", 1)[-1]
        if wheel_filename.endswith(".whl"):
            name, version = parse_wheel_filename(wheel_filename)[:2]
            assert name == key
            assert version == Version(pkg.version)

        if check_depends:
            # pyodide.loadPackage() can only resolve dependencies in the lockfile.
            # It normalizes names on lookup, and the lockfile shipped with
            # Pyodide does contain some non-normalized names in depends.
            missing = [
                dep
                for dep in pkg.depends
                if canonicalize_name(dep) not in lockfile.packages
            ]
            assert not missing, f"{key} depends on packages not in the lockfile"

    return lockfile


def _assert_micropip_package(lockfile, wheel, *, depends, imports):
    pkg = lockfile.packages[canonicalize_name(wheel.name)]
    assert pkg.name == wheel.name
    assert pkg.version == wheel.version
    assert pkg.file_name == wheel.url
    assert pkg.sha256 == hashlib.sha256(wheel.content).hexdigest()
    assert pkg.install_dir == "site"
    assert pkg.package_type == "package"
    assert not pkg.unvendored_tests
    assert pkg.depends == depends
    assert pkg.imports == imports


@pytest.mark.parametrize("deps", [True, False])
def test_freeze_pyodide_lock_spec(selenium_standalone_micropip, fake_index, deps):
    """
    freeze() should produce a valid pyodide-lock.json containing the packages
    installed with micropip, the packages of the original lockfile, and the
    original info section.
    """
    # "six" is in the Pyodide lockfile, so it is loaded with pyodide.loadPackage
    dummy = fake_index.add_pkg_version(
        "dummy",
        requirements=["dep1", "dep2", "six"],
        top_level=FREEZE_TOPLEVEL["dummy"],
    )
    dep1 = fake_index.add_pkg_version("dep1", top_level=FREEZE_TOPLEVEL["dep1"])
    dep2 = fake_index.add_pkg_version("dep2", top_level=FREEZE_TOPLEVEL["dep2"])

    requirements = ["dummy"] if deps else ["dummy", "dep1", "dep2", "six"]
    result = _install_and_freeze(
        selenium_standalone_micropip, requirements, fake_index.url, deps
    )
    lockfile = _parse_lockfile(result["frozen"])

    _assert_micropip_package(
        lockfile,
        dummy,
        depends=["dep1", "dep2", "six"],
        imports=FREEZE_TOPLEVEL["dummy"],
    )
    for wheel in (dep1, dep2):
        _assert_micropip_package(
            lockfile, wheel, depends=[], imports=FREEZE_TOPLEVEL[wheel.name]
        )

    assert lockfile.info.to_dict() == json.loads(result["orig_info"])

    # Packages of the original lockfile are kept as they are, except that
    # file names are made absolute using the lockfile base URL.
    from pyodide_lock import PackageSpec

    orig_packages = json.loads(result["orig_packages"])
    assert set(lockfile.packages) == set(orig_packages) | {"dummy", "dep1", "dep2"}
    for name, orig in orig_packages.items():
        orig["file_name"] = urljoin(result["base_url"], orig["file_name"])
        assert lockfile.packages[name] == PackageSpec.from_dict(orig)


@pytest.mark.parametrize("deps", [True, False])
def test_freeze_pyodide_lock_spec_non_normalized_names(
    selenium_standalone_micropip, fake_index, deps
):
    """
    Lockfile keys and depends entries are normalized names, even when
    the package metadata uses non-normalized ones.
    """
    pkg = fake_index.add_pkg_version("Dummy_Pkg", requirements=["Dep.One"])
    dep = fake_index.add_pkg_version("Dep.One", top_level=["dep_one"])

    requirements = ["dummy-pkg"] if deps else ["dummy-pkg", "dep-one"]
    result = _install_and_freeze(
        selenium_standalone_micropip, requirements, fake_index.url, deps
    )
    lockfile = _parse_lockfile(result["frozen"])

    _assert_micropip_package(lockfile, pkg, depends=["dep-one"], imports=[])
    _assert_micropip_package(lockfile, dep, depends=[], imports=["dep_one"])


def test_freeze_pyodide_lock_spec_extras(selenium_standalone_micropip, fake_index):
    """Dependencies required by a requested extra are recorded in depends."""
    pkg = fake_index.add_pkg_version(
        "dummy", requirements=["dep1"], extras={"feature": ["dep2"], "other": ["dep3"]}
    )
    dep1 = fake_index.add_pkg_version("dep1")
    dep2 = fake_index.add_pkg_version("dep2")
    fake_index.add_pkg_version("dep3")

    result = _install_and_freeze(
        selenium_standalone_micropip, ["dummy[feature]"], fake_index.url
    )
    lockfile = _parse_lockfile(result["frozen"])

    _assert_micropip_package(lockfile, pkg, depends=["dep1", "dep2"], imports=[])
    _assert_micropip_package(lockfile, dep1, depends=[], imports=[])
    _assert_micropip_package(lockfile, dep2, depends=[], imports=[])
    assert "dep3" not in lockfile.packages


def test_freeze_pyodide_lock_spec_missing_dependency(
    selenium_standalone_micropip, fake_index
):
    """
    freeze() should not fail when a dependency of a package installed with
    deps=False is not installed. The declared dependencies are still recorded.
    """
    pkg = fake_index.add_pkg_version("dummy", requirements=["dep1", "six"])
    fake_index.add_pkg_version("dep1")

    result = _install_and_freeze(
        selenium_standalone_micropip, ["dummy"], fake_index.url, deps=False
    )
    lockfile = _parse_lockfile(result["frozen"], check_depends=False)

    _assert_micropip_package(lockfile, pkg, depends=["dep1", "six"], imports=[])
    assert "dep1" not in lockfile.packages
    # six is not loaded, but it is still in the lockfile
    assert "six" in lockfile.packages


def test_freeze_pyodide_lock_spec_other_installer(
    selenium_standalone_micropip, fake_index
):
    """
    Only packages installed with micropip (or pyodide.loadPackage) end up in
    the lockfile. Packages installed by other means, e.g. with pip in a
    Pyodide virtual environment (#107), have no wheel URL to lock, so they
    are left out.
    """
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url):
        import importlib.metadata
        import site
        from pathlib import Path

        import micropip

        await micropip.install("dummy", index_urls=[index_url])

        dist_info = Path(site.getsitepackages()[0]) / "other_pkg-1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: other-pkg\nVersion: 1.0\n"
        )
        (dist_info / "INSTALLER").write_text("pip\n")
        assert importlib.metadata.version("other-pkg") == "1.0"

        return micropip.freeze()

    lockfile = _parse_lockfile(run(selenium_standalone_micropip, fake_index.url))

    _assert_micropip_package(lockfile, wheel, depends=[], imports=[])
    assert "other-pkg" not in lockfile.packages
