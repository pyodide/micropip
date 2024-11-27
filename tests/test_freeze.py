import pytest
from conftest import mock_fetch_cls


@pytest.mark.asyncio
async def test_freeze(mock_fetch: mock_fetch_cls, mock_importlib: None) -> None:
    import micropip

    dummy = "dummy"
    dep1 = "dep1"
    dep2 = "dep2"
    toplevel = [["abc", "def", "geh"], ["c", "h", "i"], ["a12", "b13"]]

    mock_fetch.add_pkg_version(dummy, requirements=[dep1, dep2], top_level=toplevel[0])
    mock_fetch.add_pkg_version(dep1, top_level=toplevel[1])
    mock_fetch.add_pkg_version(dep2, top_level=toplevel[2])

    await micropip.install(dummy)

    import json

    lockfile = json.loads(micropip.freeze())

    pkg_metadata = lockfile["packages"][dummy]
    dep1_metadata = lockfile["packages"][dep1]
    dep2_metadata = lockfile["packages"][dep2]
    assert pkg_metadata["depends"] == [dep1, dep2]
    assert dep1_metadata["depends"] == []
    assert dep2_metadata["depends"] == []
    assert pkg_metadata["imports"] == toplevel[0]
    assert dep1_metadata["imports"] == toplevel[1]
    assert dep2_metadata["imports"] == toplevel[2]


@pytest.mark.asyncio
async def test_freeze_fix_depends(
    mock_fetch: mock_fetch_cls, mock_importlib: None
) -> None:
    import micropip

    dummy = "dummy"
    dep1 = "dep1"
    dep2 = "dep2"
    toplevel = [["abc", "def", "geh"], ["c", "h", "i"], ["a12", "b13"]]

    mock_fetch.add_pkg_version(dummy, requirements=[dep1, dep2], top_level=toplevel[0])
    mock_fetch.add_pkg_version(dep1, top_level=toplevel[1])
    mock_fetch.add_pkg_version(dep2, top_level=toplevel[2])

    await micropip.install(dummy, deps=False)
    await micropip.install(dep1, deps=False)
    await micropip.install(dep2, deps=False)

    import json

    lockfile = json.loads(micropip.freeze())

    pkg_metadata = lockfile["packages"][dummy]
    dep1_metadata = lockfile["packages"][dep1]
    dep2_metadata = lockfile["packages"][dep2]
    assert pkg_metadata["depends"] == [dep1, dep2]
    assert dep1_metadata["depends"] == []
    assert dep2_metadata["depends"] == []
    assert pkg_metadata["imports"] == toplevel[0]
    assert dep1_metadata["imports"] == toplevel[1]
    assert dep2_metadata["imports"] == toplevel[2]


def test_freeze_lockfile_compat(selenium_standalone_micropip, wheel_catalog, tmp_path):
    from pyodide_lock import PyodideLockSpec

    selenium = selenium_standalone_micropip
    snowball_wheel = wheel_catalog.get("snowballstemmer")
    url = snowball_wheel.url

    lockfile_content = selenium.run_async(
        f"""
        await micropip.install("{url}")
        micropip.freeze()
    """
    )

    lockfile_path = tmp_path / "lockfile.json"
    with open(lockfile_path, "w") as f:
        f.write(lockfile_content)

    lockfile = PyodideLockSpec.from_json(lockfile_path)
    assert lockfile.packages["snowballstemmer"].file_name == url
    assert lockfile.packages["snowballstemmer"].name == "snowballstemmer"
    assert lockfile.packages["snowballstemmer"].depends == []
    assert lockfile.packages["snowballstemmer"].imports == ["snowballstemmer"]
    assert lockfile.packages["snowballstemmer"].install_dir == "site"
    assert not lockfile.packages["snowballstemmer"].unvendored_tests
    assert lockfile.packages["snowballstemmer"].version == snowball_wheel.version
