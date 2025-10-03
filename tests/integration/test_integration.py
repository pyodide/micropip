# Integration tests for micropip
# These test often requires querying to the real packages existing in PyPI,
# to test the micropip's ability to install packages from real world package indexes.

# To prevent sending many requests to remote servers, these tests are disabled by default.
# To run these tests locally, invoke pytest with the `--integration` flag.

import pytest
from pytest_pyodide import run_in_pyodide


def integration_test_only(func):
    def wrapper(selenium_standalone_micropip, pytestconfig):
        if not pytestconfig.getoption("--integration"):
            pytest.skip("Integration tests are skipped. Use --integration to run them.")
        func(selenium_standalone_micropip, pytestconfig)

    return wrapper


@integration_test_only
def test_integration_install_basic(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_install_no_deps(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("pyodide-micropip-test", deps=False)

        try:
            # pyodide-micropip-test depends on snowballstemmer
            import snowballstemmer  # noqa: F401
        except ModuleNotFoundError:
            pass
        else:
            raise Exception("Should raise!")

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_install_reinstall(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("mccabe==0.6.1")

        import mccabe

        assert mccabe.__version__ == "0.6.1"

        try:
            await micropip.install("mccabe==0.7.0", reinstall=False)
        except ValueError as e:
            assert "already installed" in str(e)
        else:
            raise Exception("Should raise!")

        await micropip.install("mccabe==0.7.0", reinstall=True)

        import mccabe

        # still 0.6.1
        assert mccabe.__version__ == "0.6.1"

        import importlib

        importlib.reload(mccabe)

        assert mccabe.__version__ == "0.7.0"

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_install_yanked(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import contextlib
        import io

        import micropip

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            # install yanked version
            await micropip.install("black==21.11b0", verbose=True)

            captured = buf.getvalue()
            assert "The candidate selected for download or install is a" in captured
            assert "'black' candidate (version 21.11b0" in captured

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_list_basic(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        packages = micropip.list()
        assert "snowballstemmer" in packages

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_uninstall_basic(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

        micropip.uninstall("snowballstemmer")

        packages = micropip.list()
        assert "snowballstemmer" not in packages

    _run(selenium_standalone_micropip)


@integration_test_only
def test_integration_freeze_basic(selenium_standalone_micropip, pytestconfig):
    @run_in_pyodide
    async def _run(selenium):
        import json

        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

        lockfile = micropip.freeze()
        assert "snowballstemmer" in json.loads(lockfile)["packages"]

    _run(selenium_standalone_micropip)


@integration_test_only
def test_installer(selenium_standalone_micropip, pytestconfig):

    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        from importlib.metadata import distribution

        dummy_wheel = distribution("snowballstemmer")
        assert dummy_wheel.name == "snowballstemmer"

        dist_dir = dummy_wheel._path

        assert (dist_dir / "INSTALLER").read_text() == "micropip"
        assert (dist_dir / "PYODIDE_SOURCE").exists()
        assert (dist_dir / "PYODIDE_URL").exists()
        assert (dist_dir / "PYODIDE_SHA256").exists()

    _run(selenium_standalone_micropip)


@integration_test_only
def test_install_url_based_wheel(selenium_standalone_micropip):
    # Dependencies of URL based wheels are fetched from PyPI. It is tricky to test this without accessing PyPI, hence integration test
    @run_in_pyodide
    async def run(selenium, url):
        import micropip

        await micropip.install(f"typer @ {url}")

        try:
            import rich
        except ModuleNotFoundError:
            pass
        else:
            raise Exception("Should raise!")
        
        await micropip.uninstall("typer")

        await micropip.install(f"typer[all] @ {url}")

        import typer
        import rich


    # typer 0.10.0 has "[all]" dependency that comes with colorama, shellingham, and rich 
    typer_0_10_0_url = "https://files.pythonhosted.org/packages/d9/07/8100c125307a26f03c305764f22cd995ae1878071ddf1df3588add73b53c/typer-0.10.0-py3-none-any.whl"
    _run(selenium_standalone_micropip, typer_0_10_0_url)