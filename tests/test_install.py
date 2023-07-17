from pathlib import Path

import pytest
from conftest import SNOWBALL_WHEEL, mock_fetch_cls
from packaging.utils import parse_wheel_filename
from pytest_pyodide import run_in_pyodide, spawn_web_server

import micropip


def test_install_simple(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    assert (
        selenium.run_js(
            """
            return await pyodide.runPythonAsync(`
                import os
                import micropip
                from pyodide.ffi import to_js
                # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
                # It is used to test markers support
                await micropip.install('pyodide-micropip-test')
                import snowballstemmer
                stemmer = snowballstemmer.stemmer('english')
                to_js(stemmer.stemWords('go going goes gone'.split()))
            `);
            """
        )
        == ["go", "go", "goe", "gone"]
    )


@pytest.mark.parametrize("base_url", ["'{base_url}'", "'.'"])
def test_install_custom_url(selenium_standalone_micropip, base_url):
    selenium = selenium_standalone_micropip

    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + SNOWBALL_WHEEL

        selenium.run_js(
            f"""
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('{url}')
                import snowballstemmer
            `);
            """
        )


@pytest.mark.xfail_browsers(chrome="node only", firefox="node only")
def test_install_file_protocol_node(selenium_standalone_micropip, request):
    selenium = selenium_standalone_micropip
    DIST_PATH = request.config.option.dist_dir

    pyparsing_wheel_name = list(DIST_PATH.glob("pyparsing*.whl"))[0].name
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install('file:{pyparsing_wheel_name}')
            import pyparsing
        `);
        """
    )


def test_install_different_version(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "https://files.pythonhosted.org/packages/89/06/2c2d3034b4d6bf22f2a4ae546d16925898658a33b4400cfb7e2c1e2871a3/pytz-2020.5-py2.py3-none-any.whl"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


def test_install_different_version2(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "pytz == 2020.5"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_install_mixed_case2(selenium_standalone_micropip, jinja2):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        f"""
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install("{jinja2}")
            import jinja2
        `);
        """
    )


@pytest.mark.asyncio
async def test_package_with_extra(mock_fetch):
    mock_fetch.add_pkg_version("depa")
    mock_fetch.add_pkg_version("depb")
    mock_fetch.add_pkg_version("pkga", extras={"opt_feature": ["depa"]})
    mock_fetch.add_pkg_version("pkgb", extras={"opt_feature": ["depb"]})

    await micropip.install(["pkga[opt_feature]", "pkgb"])

    pkg_list = micropip.list()

    assert "pkga" in pkg_list
    assert "depa" in pkg_list

    assert "pkgb" in pkg_list
    assert "depb" not in pkg_list


@pytest.mark.asyncio
async def test_package_with_extra_all(mock_fetch):
    mock_fetch.add_pkg_version("depa")
    mock_fetch.add_pkg_version("depb")
    mock_fetch.add_pkg_version("depc")
    mock_fetch.add_pkg_version("depd")

    mock_fetch.add_pkg_version("pkga", extras={"all": ["depa", "depb"]})
    mock_fetch.add_pkg_version(
        "pkgb", extras={"opt_feature": ["depc"], "all": ["depc", "depd"]}
    )

    await micropip.install(["pkga[all]", "pkgb[opt_feature]"])

    pkg_list = micropip.list()
    assert "depa" in pkg_list
    assert "depb" in pkg_list

    assert "depc" in pkg_list
    assert "depd" not in pkg_list


@pytest.mark.parametrize("transitive_req", [True, False])
@pytest.mark.asyncio
async def test_package_with_extra_transitive(
    mock_fetch, transitive_req, mock_importlib
):
    mock_fetch.add_pkg_version("depb")

    pkga_optional_dep = "depa[opt_feature]" if transitive_req else "depa"
    mock_fetch.add_pkg_version("depa", extras={"opt_feature": ["depb"]})
    mock_fetch.add_pkg_version("pkga", extras={"opt_feature": [pkga_optional_dep]})

    await micropip.install(["pkga[opt_feature]"])
    pkg_list = micropip.list()
    assert "depa" in pkg_list
    if transitive_req:
        assert "depb" in pkg_list
    else:
        assert "depb" not in pkg_list


@pytest.mark.asyncio
async def test_install_keep_going(mock_fetch: mock_fetch_cls) -> None:
    dummy = "dummy"
    dep1 = "dep1"
    dep2 = "dep2"
    mock_fetch.add_pkg_version(dummy, requirements=[dep1, dep2])
    mock_fetch.add_pkg_version(dep1, platform="invalid")
    mock_fetch.add_pkg_version(dep2, platform="invalid")

    # report order is non-deterministic
    msg = f"({dep1}|{dep2}).*({dep2}|{dep1})"
    with pytest.raises(ValueError, match=msg):
        await micropip.install(dummy, keep_going=True)


@pytest.mark.asyncio
async def test_install_version_compare_prerelease(mock_fetch: mock_fetch_cls) -> None:
    dummy = "dummy"
    version_old = "3.2.0"
    version_new = "3.2.1a1"

    mock_fetch.add_pkg_version(dummy, version_old)
    mock_fetch.add_pkg_version(dummy, version_new)

    await micropip.install(f"{dummy}=={version_new}")
    await micropip.install(f"{dummy}>={version_old}")

    installed_pkgs = micropip.list()
    # Older version should not be installed
    assert installed_pkgs[dummy].version == version_new


@pytest.mark.asyncio
async def test_install_no_deps(mock_fetch: mock_fetch_cls) -> None:
    dummy = "dummy"
    dep = "dep"
    mock_fetch.add_pkg_version(dummy, requirements=[dep])
    mock_fetch.add_pkg_version(dep)

    await micropip.install(dummy, deps=False)

    assert dummy in micropip.list()
    assert dep not in micropip.list()


@pytest.mark.asyncio
@pytest.mark.parametrize("pre", [True, False])
async def test_install_pre(
    mock_fetch: mock_fetch_cls,
    pre: bool,
) -> None:
    dummy = "dummy"
    version_alpha = "2.0.1a1"
    version_stable = "1.0.0"

    version_should_select = version_alpha if pre else version_stable

    mock_fetch.add_pkg_version(dummy, version_stable)
    mock_fetch.add_pkg_version(dummy, version_alpha)
    await micropip.install(dummy, pre=pre)
    assert micropip.list()[dummy].version == version_should_select


@pytest.mark.asyncio
async def test_fetch_wheel_fail(monkeypatch, wheel_base):
    pytest.importorskip("packaging")
    import micropip
    from micropip import transaction

    def _mock_fetch_bytes(arg, *args, **kwargs):
        raise OSError(f"Request for {arg} failed with status 404: Not Found")

    monkeypatch.setattr(transaction, "fetch_bytes", _mock_fetch_bytes)

    msg = "Access-Control-Allow-Origin"
    with pytest.raises(ValueError, match=msg):
        await micropip.install("htps://x.com/xxx-1.0.0-py3-none-any.whl")


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_install_with_credentials(selenium):
    import json
    from unittest.mock import MagicMock, patch

    import micropip

    fetch_response_mock = MagicMock()

    async def myfunc():
        return json.dumps(dict())

    fetch_response_mock.string.side_effect = myfunc

    @patch("micropip._compat_in_pyodide.pyfetch", return_value=fetch_response_mock)
    async def call_micropip_install(pyfetch_mock):
        try:
            await micropip.install("pyodide-micropip-test", credentials="include")
        except BaseException:
            # The above will raise an exception as the mock data is garbage
            # but it is sufficient for this test
            pass
        pyfetch_mock.assert_called_with(
            "https://pypi.org/pypi/pyodide-micropip-test/json", credentials="include"
        )

    await call_micropip_install()


@pytest.mark.asyncio
async def test_load_binary_wheel1(
    mock_fetch: mock_fetch_cls, mock_importlib: None, mock_platform: None
) -> None:
    dummy = "dummy"
    mock_fetch.add_pkg_version(dummy, platform="emscripten")
    await micropip.install(dummy)


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_load_binary_wheel2(selenium):
    from pyodide_js._api import repodata_packages

    import micropip

    await micropip.install(repodata_packages.regex.file_name)
    import regex  # noqa: F401


def test_emfs(selenium_standalone_micropip):
    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server
        url = f"http://{server_hostname}:{server_port}/"

        @run_in_pyodide(packages=["micropip"])
        async def run_test(selenium, url, wheel_name):
            from pyodide.http import pyfetch

            import micropip

            resp = await pyfetch(url + wheel_name)
            await resp._into_file(open(wheel_name, "wb"))
            await micropip.install("emfs:" + wheel_name)
            import snowballstemmer

            stemmer = snowballstemmer.stemmer("english")
            assert stemmer.stemWords("go going goes gone".split()) == [
                "go",
                "go",
                "goe",
                "gone",
            ]

        run_test(selenium_standalone_micropip, url, SNOWBALL_WHEEL)


def test_logging(selenium_standalone_micropip):
    # TODO: make a fixture for this, it's used in a few places
    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server
        url = f"http://{server_hostname}:{server_port}/"
        wheel_url = url + SNOWBALL_WHEEL
        name, version, _, _ = parse_wheel_filename(SNOWBALL_WHEEL)

        @run_in_pyodide(packages=["micropip"])
        async def run_test(selenium, url, name, version):
            import contextlib
            import io

            import micropip

            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                await micropip.install(url, verbose=True)

                captured = buf.getvalue()

                assert f"Collecting {name}" in captured
                assert f"  Downloading {name}" in captured
                assert f"Installing collected packages: {name}" in captured
                assert f"Successfully installed {name}-{version}" in captured

        run_test(selenium_standalone_micropip, wheel_url, name, version)


@pytest.mark.asyncio
async def test_custom_index_urls(mock_package_index_json_api, monkeypatch):
    from io import BytesIO

    mock_server_fake_package = mock_package_index_json_api(
        pkgs=["fake-pkg-micropip-test"]
    )

    _wheel_url = ""

    async def _mock_fetch_bytes(url, *args):
        nonlocal _wheel_url
        _wheel_url = url
        return BytesIO(b"fake wheel")

    from micropip import transaction

    monkeypatch.setattr(transaction, "fetch_bytes", _mock_fetch_bytes)

    try:
        await micropip.install(
            "fake-pkg-micropip-test", index_urls=[mock_server_fake_package]
        )
    except Exception:
        # We just check that the custom index url was used
        # install will fail because the package is not real, but it doesn't matter.
        pass

    assert "fake_pkg_micropip_test-1.0.0-py2.py3-none-any.whl" in _wheel_url
