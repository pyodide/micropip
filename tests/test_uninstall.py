import pytest
from pytest_pyodide import run_in_pyodide

SNOWBALL_WHEEL = "snowballstemmer-2.0.0-py2.py3-none-any.whl"


@pytest.mark.asyncio
async def test_uninstall(selenium_standalone_micropip, wheel_server_url):
    @run_in_pyodide()
    async def run(wheel, wheel_server_url):
        import micropip

        wheel_url = wheel_server_url + wheel
        await micropip.install(wheel_url)

        assert "snowballstemmer" in micropip.list()

        micropip.uninstall("snowballstemmer")

        assert "snowballstemmer" not in micropip.list()

    await run(SNOWBALL_WHEEL, wheel_server_url)
