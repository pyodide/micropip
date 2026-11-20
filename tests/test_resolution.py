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
