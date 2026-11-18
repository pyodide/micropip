import pytest
from pytest_pyodide import run_in_pyodide

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
