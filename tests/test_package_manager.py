import json

import pytest
from conftest import mock_fetch_cls

import micropip.package_index as package_index
from micropip.package_manager import PackageManager


def get_test_package_manager() -> PackageManager:
    package_manager = PackageManager()

    # TODO: inject necessary constructor parameters

    return package_manager


def test_set_index_urls():
    manager = get_test_package_manager()

    default_index_urls = package_index.DEFAULT_INDEX_URLS
    assert manager.index_urls == default_index_urls

    valid_url1 = "https://pkg-index.com/{package_name}/json/"
    valid_url2 = "https://another-pkg-index.com/{package_name}"
    valid_url3 = "https://another-pkg-index.com/simple/"
    try:
        manager.set_index_urls(valid_url1)
        assert manager.index_urls == [valid_url1]

        manager.set_index_urls([valid_url1, valid_url2, valid_url3])
        assert manager.index_urls == [valid_url1, valid_url2, valid_url3]
    finally:
        manager.set_index_urls(default_index_urls)
        assert manager.index_urls == default_index_urls


def test_freeze():
    manager = get_test_package_manager()

    test_repodata_info = {
        "test-dep-1": "0.1.0",
        "test-dep-2": "0.2.0",
    }
    test_repodata_packages = {
        "test-dep-1": {
            "version": "0.1.0",
            "depends": ["test-dep-2"],
        },
        "test-dep-2": {
            "version": "0.2.0",
        },
    }

    manager.repodata_info = test_repodata_info.copy()
    manager.repodata_packages = test_repodata_packages.copy()

    lockfile = manager.freeze()
    assert json.loads(lockfile) == {
        "info": test_repodata_info,
        "packages": test_repodata_packages,
    }


@pytest.mark.asyncio
async def test_list(mock_fetch: mock_fetch_cls):
    manager = get_test_package_manager()

    dummy = "dummy"
    mock_fetch.add_pkg_version(dummy)
    dummy_url = f"https://dummy.com/{dummy}-1.0.0-py3-none-any.whl"

    await manager.install(dummy_url)

    pkg_list = manager.list()

    assert dummy in pkg_list
    assert pkg_list[dummy].source.lower() == dummy_url


@pytest.mark.asyncio
async def test_custom_index_url(mock_package_index_json_api, monkeypatch):
    manager = get_test_package_manager()

    mock_server_fake_package = mock_package_index_json_api(
        pkgs=["fake-pkg-micropip-test"]
    )

    _wheel_url = ""

    async def _mock_fetch_bytes(url, *args):
        nonlocal _wheel_url
        _wheel_url = url
        return b"fake wheel"

    from micropip import wheelinfo

    monkeypatch.setattr(wheelinfo, "fetch_bytes", _mock_fetch_bytes)

    manager.set_index_urls([mock_server_fake_package])

    try:
        await manager.install("fake-pkg-micropip-test")
    except Exception:
        # We just check that the custom index url was used
        # install will fail because the package is not real, but it doesn't matter.
        pass

    assert "fake_pkg_micropip_test-1.0.0-py2.py3-none-any.whl" in _wheel_url
