from pathlib import Path

import pytest
from conftest import SNOWBALL_WHEEL, mock_fetch_cls
from pytest_pyodide import spawn_web_server

import micropip


@pytest.mark.asyncio
async def test_list_pypi_package(mock_fetch: mock_fetch_cls) -> None:
    dummy = "dummy"
    mock_fetch.add_pkg_version(dummy)

    await micropip.install(dummy)
    pkg_list = micropip.list()
    assert dummy in pkg_list
    assert pkg_list[dummy].source.lower() == "pypi"


@pytest.mark.asyncio
async def test_list_wheel_package(mock_fetch: mock_fetch_cls) -> None:
    dummy = "dummy"
    mock_fetch.add_pkg_version(dummy)
    dummy_url = f"https://dummy.com/{dummy}-1.0.0-py3-none-any.whl"

    await micropip.install(dummy_url)

    pkg_list = micropip.list()
    assert dummy in pkg_list
    assert pkg_list[dummy].source.lower() == dummy_url


@pytest.mark.asyncio
async def test_list_wheel_name_mismatch(mock_fetch: mock_fetch_cls) -> None:
    dummy_pkg_name = "dummy-Dummy"
    mock_fetch.add_pkg_version(dummy_pkg_name)
    dummy_url = "https://dummy.com/dummy_dummy-1.0.0-py3-none-any.whl"

    await micropip.install(dummy_url)

    pkg_list = micropip.list()
    assert dummy_pkg_name in pkg_list
    assert pkg_list[dummy_pkg_name].source.lower() == dummy_url


def test_list_load_package_from_url(selenium_standalone_micropip):
    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + SNOWBALL_WHEEL

        selenium = selenium_standalone_micropip
        selenium.run_js(
            f"""
            await pyodide.loadPackage({url!r});
            await pyodide.runPythonAsync(`
                import micropip
                assert "snowballstemmer" in micropip.list()
            `);
            """
        )


def test_list_pyodide_package(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "regex"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


def test_list_loaded_from_js(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.loadPackage("regex");
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )
