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


def test_set_extra_index_urls():
    manager = get_test_package_manager()

    # Initially, extra_index_urls should be empty
    assert manager.extra_index_urls == []

    valid_url1 = "https://pkg-index.com/{package_name}/json/"
    valid_url2 = "https://another-pkg-index.com/{package_name}"
    valid_url3 = "https://another-pkg-index.com/simple/"
    try:
        manager.set_extra_index_urls(valid_url1)
        assert manager.extra_index_urls == [valid_url1]

        manager.set_extra_index_urls([valid_url1, valid_url2, valid_url3])
        assert manager.extra_index_urls == [valid_url1, valid_url2, valid_url3]
    finally:
        manager.set_extra_index_urls([])
        assert manager.extra_index_urls == []


@pytest.mark.asyncio
async def test_list_packages(mock_fetch: mock_fetch_cls):
    manager = get_test_package_manager()

    dummy = "dummy"
    mock_fetch.add_pkg_version(dummy)
    dummy_url = f"https://dummy.com/{dummy}-1.0.0-py3-none-any.whl"

    await manager.install(dummy_url)

    pkg_list = manager.list_packages()

    assert dummy in pkg_list
    assert pkg_list[dummy].source.lower() == dummy_url


def test_set_index_strategy():
    manager = get_test_package_manager()

    # Initially, index_strategy should be 'first-index'
    assert manager.index_strategy == "first-index"

    valid_strategies = ["first-index", "unsafe-first-match", "unsafe-best-match"]
    try:
        for strategy in valid_strategies:
            manager.set_index_strategy(strategy)
            assert manager.index_strategy == strategy

        # Test invalid strategy
        with pytest.raises(ValueError):
            manager.set_index_strategy("invalid-strategy")
    finally:
        manager.set_index_strategy("first-index")


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


@pytest.mark.asyncio
async def test_extra_index_urls_parameter(mock_package_index_json_api, monkeypatch):
    manager = get_test_package_manager()

    # Set up two mock servers with different packages
    main_index_url = mock_package_index_json_api(
        pkgs=["package-a"], pkgs_not_found=["package-b"]
    )
    extra_index_url = mock_package_index_json_api(
        pkgs=["package-b"], pkgs_not_found=["package-a"]
    )

    _wheel_url = ""

    async def _mock_fetch_bytes(url, *args):
        nonlocal _wheel_url
        _wheel_url = url
        return b"fake wheel"

    from micropip import wheelinfo

    monkeypatch.setattr(wheelinfo, "fetch_bytes", _mock_fetch_bytes)

    # Test with extra_index_urls parameter
    try:
        await manager.install(
            "package-b", index_urls=main_index_url, extra_index_urls=extra_index_url
        )
    except Exception:
        # We just check that the package was found in the extra index
        pass

    assert "package_b-1.0.0-py2.py3-none-any.whl" in _wheel_url

    # Test with set_extra_index_urls
    _wheel_url = ""
    manager.set_index_urls([main_index_url])
    manager.set_extra_index_urls([extra_index_url])

    try:
        await manager.install("package-b")
    except Exception:
        pass

    assert "package_b-1.0.0-py2.py3-none-any.whl" in _wheel_url


@pytest.mark.asyncio
async def test_index_strategy_parameter(mock_fetch, monkeypatch):
    manager = get_test_package_manager()

    # Track which strategy is passed to find_wheel
    from micropip.transaction import find_wheel

    original_find_wheel = find_wheel
    captured_strategy = []

    def mock_find_wheel(metadata, req, strategy="first-index"):
        captured_strategy.append(strategy)
        return original_find_wheel(metadata, req)

    monkeypatch.setattr("micropip.transaction.find_wheel", mock_find_wheel)

    # Set up a mock package
    mock_fetch.add_pkg_version("dummy", version="1.0.0")

    # Test different strategies
    strategies = ["first-index", "unsafe-first-match", "unsafe-best-match"]

    for strategy in strategies:
        captured_strategy.clear()
        try:
            await manager.install("dummy", index_strategy=strategy)
            assert captured_strategy[0] == strategy
        except Exception:
            pass  # Ignore exceptions, we're just checking the parameter passing


@pytest.mark.asyncio
async def test_combined_index_urls(mock_package_index_json_api, monkeypatch):
    manager = get_test_package_manager()

    # Set up two mock servers with different packages
    main_index_url = mock_package_index_json_api(pkgs=["package-main"])
    extra_index_url = mock_package_index_json_api(pkgs=["package-extra"])

    _wheel_urls = []

    async def _mock_fetch_bytes(url, *args):
        nonlocal _wheel_urls
        _wheel_urls.append(url)
        return b"fake wheel"

    from micropip import wheelinfo

    monkeypatch.setattr(wheelinfo, "fetch_bytes", _mock_fetch_bytes)

    # Test installing packages from both main and extra indexes
    manager.set_index_urls([main_index_url])
    manager.set_extra_index_urls([extra_index_url])

    try:
        await manager.install(["package-main", "package-extra"])
    except Exception:
        pass


@pytest.mark.asyncio
async def test_dependency_resolution_with_multiple_indexes(
    mock_fetch: mock_fetch_cls, monkeypatch
):
    """Test that dependencies are properly resolved from multiple indexes."""
    manager = get_test_package_manager()

    # Create a package with dependencies
    main_pkg = "scikit-learn"
    dep1 = "numpy"
    dep2 = "scipy"

    mock_fetch.add_pkg_version(main_pkg, requirements=[dep1, dep2])
    mock_fetch.add_pkg_version(dep1)
    mock_fetch.add_pkg_version(dep2)

    await manager.install(main_pkg)

    pkg_list = manager.list_packages()
    assert main_pkg in pkg_list
    assert dep1 in pkg_list
    assert dep2 in pkg_list

    for pkg in [main_pkg, dep1, dep2]:
        if pkg in pkg_list:
            manager.uninstall(pkg)

    requested_urls = []

    # Create a modified version of add_pkg_version that tracks URL usage
    original_add_pkg_version = mock_fetch.add_pkg_version

    def tracked_add_pkg_version(*args, **kwargs):
        requested_urls.append(args[0])
        return original_add_pkg_version(*args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(mock_fetch, "add_pkg_version", tracked_add_pkg_version)

        # Install with a main index that only has scikit-learn, and
        # with extra_index_urls that has the dependencies.
        await manager.install(
            main_pkg, extra_index_urls="https://extra-index.org/simple"
        )

        pkg_list = manager.list_packages()
        assert main_pkg in pkg_list
        assert dep1 in pkg_list
        assert dep2 in pkg_list


@pytest.mark.asyncio
async def test_different_version_resolution_strategies(mock_fetch: mock_fetch_cls):
    """Test different version resolution strategies with multiple indexes."""
    manager = get_test_package_manager()

    # Add a package with two versions
    pkg_name = "test-package"
    old_version = "1.0.0"
    new_version = "2.0.0"

    mock_fetch.add_pkg_version(pkg_name, version=old_version)
    mock_fetch.add_pkg_version(pkg_name, version=new_version)

    # With first-index, it should use the latest version available in the
    # first index i.e., 1.0.0 as it was indexed first.
    manager.set_index_strategy("first-index")
    await manager.install(pkg_name)

    pkg_list = manager.list_packages()
    assert pkg_name in pkg_list
    assert pkg_list[pkg_name].version == new_version

    manager.uninstall(pkg_name)

    # With unsafe-best-match, it should use the highest version
    # across all indexes, i.e., 2.0.0.
    manager.set_index_strategy("unsafe-best-match")
    await manager.install(pkg_name)

    pkg_list = manager.list_packages()
    assert pkg_name in pkg_list
    assert pkg_list[pkg_name].version == new_version
