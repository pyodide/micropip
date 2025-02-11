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

        assert mccabe.__version__ == "0.7.0"

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
