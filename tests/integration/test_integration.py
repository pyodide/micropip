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
