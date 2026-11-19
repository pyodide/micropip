import pytest
from pytest_pyodide import run_in_pyodide

import micropip.package_index as package_index


def test_set_index_urls(host_package_manager):
    manager = host_package_manager

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


def test_list_packages(selenium_standalone_micropip, fake_index):
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, wheel_url):
        from micropip import Client

        manager = Client()
        await manager.install(wheel_url)

        pkg_list = manager.list_packages()
        assert "dummy" in pkg_list
        assert pkg_list["dummy"].source.lower() == wheel_url.lower()

    run(selenium_standalone_micropip, wheel.url)


def test_custom_index_url(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url):
        from micropip import Client

        manager = Client()
        manager.set_index_urls([index_url])
        await manager.install("dummy")

        assert "dummy" in manager.list_packages()

    run(selenium_standalone_micropip, fake_index.url)


def test_custom_resolver_and_installer(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url):
        from micropip import Client
        from micropip.installer import Installer
        from micropip.resolver import Resolver

        queried = []
        installed = []

        class MyResolver(Resolver):
            async def query_package(self, name):
                queried.append(name)
                return await super().query_package(name)

        class MyInstaller(Installer):
            async def install_wheel(self, wheel, target):
                installed.append(wheel.name)
                await super().install_wheel(wheel, target)

        class MyClient(Client):
            resolver_class = MyResolver
            installer_class = MyInstaller

        manager = MyClient()
        manager.set_index_urls([index_url])
        await manager.install("dummy")

        assert queried == ["dummy"]
        assert installed == ["dummy"]
        assert "dummy" in manager.list_packages()

    run(selenium_standalone_micropip, fake_index.url)


def test_custom_compatibility_layer(selenium_standalone_micropip, fake_index):
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url, wheel_url):
        import micropip
        from micropip.compat import PyodideCompatibilityLayer

        class CachedCompatibilityLayer(PyodideCompatibilityLayer):
            def __init__(self, cache):
                super().__init__()
                self.cache = cache

            async def fetch(self, url, **kwargs):
                if url not in self.cache:
                    self.cache[url] = await super().fetch(url, **kwargs)
                return self.cache[url]

        cache: dict[str, bytes] = {}
        client = micropip.Client(compat=CachedCompatibilityLayer(cache))
        client.set_index_urls([index_url])
        await client.install("dummy")

        assert wheel_url in cache
        assert "dummy" in client.list_packages()

    run(selenium_standalone_micropip, fake_index.url, wheel.url)


def test_compat_module_outside_pyodide():
    import micropip
    import micropip.compat
    from micropip.package_manager import PackageManager

    assert PackageManager is micropip.Client
    assert micropip.compat.__all__ == [
        "CompatibilityLayer",
        "FetchResponse",
        "LockFile",
    ]

    with pytest.raises(ImportError, match="only available in the Pyodide runtime"):
        from micropip.compat import PyodideCompatibilityLayer  # noqa: F401

    with pytest.raises(RuntimeError, match="not running in Pyodide"):
        micropip.Client().list_packages()
