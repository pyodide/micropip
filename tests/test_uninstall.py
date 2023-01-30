import pytest
from pytest_pyodide import run_in_pyodide

SNOWBALL_WHEEL = "snowballstemmer-2.0.0-py2.py3-none-any.whl"


@pytest.mark.asyncio
async def test_uninstall_basic(selenium_standalone_micropip, wheel_server_url):
    @run_in_pyodide()
    async def run(selenium, wheel, wheel_server_url):
        import micropip

        wheel_url = wheel_server_url + wheel
        await micropip.install(wheel_url)

        assert "snowballstemmer" in micropip.list()

        micropip.uninstall("snowballstemmer")

        assert "snowballstemmer" not in micropip.list()

        try:
            import snowballstemmer

            snowballstemmer.__module__
        except ImportError:
            pass
        else:
            raise AssertionError("snowballstemmer should not be available")

    await run(selenium_standalone_micropip, SNOWBALL_WHEEL, wheel_server_url)


@pytest.mark.asyncio
async def test_uninstall_files(selenium_standalone_micropip, wheel_server_url):
    @run_in_pyodide()
    async def run(selenium, wheel, wheel_server_url):
        import importlib.metadata

        import micropip

        wheel_url = wheel_server_url + wheel
        await micropip.install(wheel_url)

        assert "snowballstemmer" in micropip.list()

        dist = importlib.metadata.distribution("snowballstemmer")
        files = dist.files

        for file in files:
            assert file.locate().is_file(), f"{file.locate()} is not a file"

        assert dist._path.is_dir(), f"{dist._path} is not a directory"

        micropip.uninstall("snowballstemmer")

        for file in files:
            assert not file.locate().is_file(), f"{file.locate()} still exists after removal"

        assert not dist._path.is_dir(), f"{dist._path} still exists after removal"

    await run(selenium_standalone_micropip, SNOWBALL_WHEEL, wheel_server_url)


@pytest.mark.asyncio
async def test_uninstall_install_again(selenium_standalone_micropip, wheel_server_url):
    @run_in_pyodide()
    async def run(selenium, wheel, wheel_server_url):
        import micropip

        wheel_url = wheel_server_url + wheel
        await micropip.install(wheel_url)

        assert "snowballstemmer" in micropip.list()

        micropip.uninstall("snowballstemmer")

        assert "snowballstemmer" not in micropip.list()

        await micropip.install(wheel_url)

        assert "snowballstemmer" in micropip.list()

        import snowballstemmer

        snowballstemmer.__module__

    await run(selenium_standalone_micropip, SNOWBALL_WHEEL, wheel_server_url)
