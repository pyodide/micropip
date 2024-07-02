import json

import pytest

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


@pytest.mark.skip(reason="Not implemented")
def test_list():
    manager = get_test_package_manager()

    _package_dict = manager.list()

    # TODO: implement test after implementing manager.install()
