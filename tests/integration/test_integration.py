# Integration tests for micropip
# These test often requires querying to the real packages existing in PyPI,
# to test the micropip's ability to install packages from real world package indexes.

# To prevent sending many requests to remote servers, these tests are disabled by default.
# To run these tests locally, invoke pytest with the `--integration` flag.

from pytest_pyodide import run_in_pyodide


def test_integration_install_basic(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--integration", skip=True)

    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

    _run(selenium_standalone_micropip)


def test_integration_list_basic(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--integration", skip=True)

    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        packages = micropip.list()
        assert "snowballstemmer" in packages

    _run(selenium_standalone_micropip)


def test_integration_uninstall_basic(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--integration", skip=True)

    @run_in_pyodide
    async def _run(selenium):
        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

        micropip.uninstall("snowballstemmer")

        packages = await micropip.list()
        assert "snowballstemmer" not in packages

    _run(selenium_standalone_micropip)


def test_integration_freeze_basic(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--integration", skip=True)

    @run_in_pyodide
    async def _run(selenium):
        import json

        import micropip

        await micropip.install("snowballstemmer")

        import snowballstemmer

        snowballstemmer.stemmer("english")

        lockfile = micropip.freeze()
        assert "snowballstemmer" in json.loads(lockfile)

    _run(selenium_standalone_micropip)
