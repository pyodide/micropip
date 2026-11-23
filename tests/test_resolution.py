from pytest_pyodide import run_in_pyodide


def test_resolve_keep_going_partial_install(selenium_standalone_micropip, fake_index):
    """resolve(keep_going=True) + install_resolution installs what can be installed."""
    fake_index.add_pkg_version("good", requirements=["good-dep"])
    fake_index.add_pkg_version("good-dep")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        client = micropip.Client()
        resolution = await client.resolve(
            ["good", "not-on-the-index"], keep_going=True, index_urls=[index_url]
        )

        assert [req.name for req in resolution.failed] == ["not-on-the-index"]
        assert sorted(pkg.name for pkg in resolution.packages) == ["good", "good-dep"]
        # Nothing is installed by resolve()
        assert "good" not in client.list_packages()

        results = [r async for r in client.install_resolution(resolution)]

        assert sorted((r.name, r.ok) for r in results) == [
            ("good", True),
            ("good-dep", True),
        ]
        assert all(r.source == "pypi" for r in results)
        assert "good" in client.list_packages()

    run(selenium_standalone_micropip, fake_index.url)


def test_install_resolution_reports_failures(selenium_standalone_micropip, fake_index):
    """A wheel that fails to install is reported, and the others are installed."""
    fake_index.add_pkg_version("ok-pkg")
    broken = fake_index.add_pkg_version("broken-pkg")

    @run_in_pyodide
    async def run(selenium, index_url, broken_filename):
        import pytest

        import micropip
        from micropip.compat import PyodideCompatibilityLayer

        class FailingLayer(PyodideCompatibilityLayer):
            async def install(self, data, filename, install_dir, metadata=None):
                if filename == broken_filename:
                    raise OSError("disk full")
                await super().install(data, filename, install_dir, metadata)

        client = micropip.Client(compat=FailingLayer())
        client.set_index_urls([index_url])

        resolution = await client.resolve(["ok-pkg", "broken-pkg"])
        results = {r.name: r async for r in client.install_resolution(resolution)}

        assert results["ok-pkg"].ok
        assert isinstance(results["broken-pkg"].error, OSError)
        assert "ok-pkg" in client.list_packages()
        assert "broken-pkg" not in client.list_packages()

        # install() raises the error
        with pytest.raises(OSError, match="disk full"):
            await micropip.Client(compat=FailingLayer()).install(
                "broken-pkg", index_urls=[index_url]
            )

    run(selenium_standalone_micropip, fake_index.url, broken.filename)


def test_install_resolution_lockfile_packages(selenium_standalone_micropip):
    """Lock file packages are reported, including ones that fail to load."""

    @run_in_pyodide
    async def run(selenium):
        import pytest

        import micropip
        from micropip.compat import LockedPackage, LockFile, PyodideCompatibilityLayer

        class PartlyFailingLockFile(LockFile):
            def __iter__(self):
                return iter(
                    [
                        LockedPackage(name="loads-fine", version="1.0.0"),
                        LockedPackage(name="fails-to-load", version="1.0.0"),
                    ]
                )

            def get(self, name):
                if name in ("loads-fine", "fails-to-load"):
                    return LockedPackage(name=name, version="1.0.0")
                return None

            async def load(self, names):
                # "fails-to-load" is silently not loaded, like pyodide.loadPackage
                return [name for name in names if name != "fails-to-load"]

            def freeze(self):
                return ""

        class Layer(PyodideCompatibilityLayer):
            def __init__(self):
                super().__init__()
                self.lockfile = PartlyFailingLockFile()

        client = micropip.Client(compat=Layer())
        resolution = await client.resolve(["loads-fine", "fails-to-load"])
        assert sorted(p.name for p in resolution.lockfile_packages) == [
            "fails-to-load",
            "loads-fine",
        ]

        results = {r.name: r async for r in client.install_resolution(resolution)}
        assert results["loads-fine"].ok
        assert results["loads-fine"].source == "pyodide"
        assert isinstance(results["fails-to-load"].error, RuntimeError)

        with pytest.raises(RuntimeError, match="Failed to load 'fails-to-load'"):
            await client.install("fails-to-load")

    run(selenium_standalone_micropip)


def test_install_resolution_reinstall(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy", "1.0.0")
    fake_index.add_pkg_version("dummy", "2.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import importlib.metadata

        import micropip

        await micropip.install("dummy==1.0.0", index_urls=[index_url])

        resolution = await micropip.default_client.resolve(
            "dummy==2.0.0", reinstall=True, index_urls=[index_url]
        )
        assert resolution.reinstall
        results = [
            r async for r in micropip.default_client.install_resolution(resolution)
        ]

        assert [(r.name, r.version, r.ok) for r in results] == [
            ("dummy", "2.0.0", True)
        ]
        assert importlib.metadata.version("dummy") == "2.0.0"

    run(selenium_standalone_micropip, fake_index.url)


def test_lockfile_load_when_loadpackage_raises(selenium_standalone_micropip):
    """
    Pyodide's loadPackage currently doesn't raise when a package fails to load.
    If a later version does, packages that loaded are still reported as loaded.
    This wraps the real loadPackage to behave like that.
    """

    @run_in_pyodide
    async def run(selenium):
        import pyodide_js
        import pytest

        import micropip
        from micropip._compat import _compat_in_pyodide

        real_load_package = _compat_in_pyodide.loadPackage

        async def raising_load_package(names, options):
            await real_load_package(names, options)
            missing = [n for n in names if not hasattr(pyodide_js.loadedPackages, n)]
            raise RuntimeError(f"failed to load {missing}")

        _compat_in_pyodide.loadPackage = raising_load_package
        try:
            pyodide_js._api.lockfile_packages.regex.file_name = "/nonexistent/regex.whl"

            client = micropip.Client()
            resolution = await client.resolve(["regex", "affine"])
            results = {r.name: r async for r in client.install_resolution(resolution)}

            assert results["affine"].ok
            assert isinstance(results["regex"].error, RuntimeError)

            # The error is raised as is when every requested package is loaded
            # (it's about something else), rather than being hidden
            with pytest.raises(RuntimeError, match=r"failed to load \[\]"):
                await client.install("toolz")
        finally:
            _compat_in_pyodide.loadPackage = real_load_package

    run(selenium_standalone_micropip)


def test_resolution_requested_by(selenium_standalone_micropip, fake_index):
    """requested_by maps each package to the top-level requirements that need it."""
    fake_index.add_pkg_version("app-a", requirements=["shared", "only-a"])
    fake_index.add_pkg_version("app-b", requirements=["shared"])
    fake_index.add_pkg_version("shared")
    fake_index.add_pkg_version("only-a")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        resolution = await micropip.Client().resolve(
            ["app-a>=1", "App_B"], index_urls=[index_url]
        )

        requested_by = {k: sorted(v) for k, v in resolution.requested_by.items()}
        # Keys are canonicalized names, values are the requirements as given
        assert requested_by == {
            "app-a": ["app-a>=1"],
            "app-b": ["App_B"],
            "shared": ["App_B", "app-a>=1"],
            "only-a": ["app-a>=1"],
        }

    run(selenium_standalone_micropip, fake_index.url)


_RECORDING_LAYER = """
from micropip.compat import PyodideCompatibilityLayer

class RecordingLayer(PyodideCompatibilityLayer):
    def __init__(self):
        super().__init__()
        self.urls = []

    async def fetch(self, url, options):
        self.urls.append(url)
        return await super().fetch(url, options)
"""


def test_resolve_does_not_download_wheels(selenium_standalone_micropip, fake_index):
    """With PEP 658 metadata, resolve() only fetches metadata; wheels are downloaded on install."""
    wheel = fake_index.add_pkg_version("dummy", requirements=["dep"])
    dep = fake_index.add_pkg_version("dep")

    @run_in_pyodide
    async def run(selenium, layer_src, index_url, wheel_urls):
        import micropip

        ns = {}
        exec(layer_src, ns)
        layer = ns["RecordingLayer"]()
        client = micropip.Client(compat=layer)

        resolution = await client.resolve("dummy", index_urls=[index_url])
        assert all(not w.downloaded for w in resolution.wheels)
        assert not any(url in layer.urls for url in wheel_urls)
        assert any(url.endswith(".metadata") for url in layer.urls)

        results = [r async for r in client.install_resolution(resolution)]
        assert all(r.ok for r in results)
        for url in wheel_urls:
            assert layer.urls.count(url) == 1

    run(
        selenium_standalone_micropip,
        _RECORDING_LAYER,
        fake_index.url,
        [wheel.url, dep.url],
    )


def test_wheel_without_metadata_downloaded_once(
    selenium_standalone_micropip, fake_index
):
    """
    Without PEP 658 metadata, the resolver downloads the wheel to read its
    metadata, and installing it doesn't download it again.
    """
    wheel = fake_index.add_pkg_version("dummy", pep658=False)

    @run_in_pyodide
    async def run(selenium, layer_src, index_url, wheel_url):
        import micropip

        ns = {}
        exec(layer_src, ns)
        layer = ns["RecordingLayer"]()
        client = micropip.Client(compat=layer)

        resolution = await client.resolve("dummy", index_urls=[index_url])
        assert resolution.wheels[0].downloaded
        results = [r async for r in client.install_resolution(resolution)]

        assert [r.ok for r in results] == [True]
        assert layer.urls.count(wheel_url) == 1
        assert not any(url.endswith(".metadata") for url in layer.urls)

    run(selenium_standalone_micropip, _RECORDING_LAYER, fake_index.url, wheel.url)


def test_missing_metadata_file_falls_back_to_wheel(
    selenium_standalone_micropip, fake_index
):
    """If the advertised PEP 658 metadata file can't be fetched, the wheel is used."""
    wheel = fake_index.add_pkg_version("dummy", requirements=["dep"])
    fake_index.add_pkg_version("dep")
    # The index says the metadata file exists, but it 404s
    del fake_index._files[f"{wheel.filename}.metadata"]

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        client = micropip.Client()
        await client.install("dummy", index_urls=[index_url])
        assert {"dummy", "dep"} <= set(client.list_packages())

    run(selenium_standalone_micropip, fake_index.url)


def test_client_resolve_passes_installed_packages(
    selenium_standalone_micropip, fake_index
):
    """Client.resolve() gives the resolver a snapshot of the installed packages."""
    fake_index.add_pkg_version("Dummy_Pkg", "1.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import importlib.metadata

        import micropip
        from micropip.resolver import Resolver

        await micropip.install("Dummy_Pkg", index_urls=[index_url])

        requests = []

        class RecordingResolver(Resolver):
            def __init__(self, compat_layer, request):
                requests.append(request)
                super().__init__(compat_layer, request)

        await micropip.Client(resolver=RecordingResolver).resolve(
            "dummy-pkg", index_urls=[index_url]
        )

        installed = requests[0].installed
        # Canonicalized names
        assert installed["dummy-pkg"] == "1.0.0"
        assert installed["micropip"] == importlib.metadata.version("micropip")

    run(selenium_standalone_micropip, fake_index.url)
