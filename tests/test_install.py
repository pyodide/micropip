import pytest
from pytest_pyodide import run_in_pyodide

from micropip._vendored.packaging.src.packaging.utils import parse_wheel_filename


def test_install_custom_url(selenium_standalone_micropip, wheel_catalog):
    selenium = selenium_standalone_micropip
    snowball_wheel = wheel_catalog.get("snowballstemmer")
    url = snowball_wheel.url

    @run_in_pyodide
    async def install_from_url(selenium, url):
        import micropip

        await micropip.install(url)
        import snowballstemmer

        snowballstemmer.stemmer("english")

    install_from_url(selenium, url)


@pytest.mark.xfail_browsers(chrome="node only", firefox="node only")
def test_install_file_protocol_node(selenium_standalone_micropip, request):
    selenium = selenium_standalone_micropip
    DIST_PATH = request.config.option.dist_dir

    pyparsing_wheel_name = list(DIST_PATH.glob("pyparsing*.whl"))[0].name
    selenium.run_js(f"""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install('file:{pyparsing_wheel_name}')
            import pyparsing
        `);
        """)


def test_install_different_version(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "https://files.pythonhosted.org/packages/89/06/2c2d3034b4d6bf22f2a4ae546d16925898658a33b4400cfb7e2c1e2871a3/pytz-2020.5-py2.py3-none-any.whl"
            );
        `);
        """)
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """)


def test_install_different_version2(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "pytz == 2020.5"
            );
        `);
        """)
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """)


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_install_mixed_case2(selenium_standalone_micropip, jinja2):
    selenium = selenium_standalone_micropip
    selenium.run_js(f"""
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install("{jinja2}")
            import jinja2
        `);
        """)


@pytest.mark.parametrize("set_constraints", [False, True])
def test_install_constraints(
    set_constraints,
    valid_constraint,
    wheel_catalog,
    run_async_py_in_js,
):
    constraints = [valid_constraint] if valid_constraint else []
    run_async_py_in_js("import micropip")

    if valid_constraint and "emfs:" in valid_constraint:
        url = wheel_catalog.get("pytest").url
        wheel = url.split("/")[-1]
        run_async_py_in_js(
            "from pyodide.http import pyfetch",
            f"resp = await pyfetch('{url}')",
            f"await resp._into_file(open('{wheel}', 'wb'))",
        )

    if set_constraints:
        run_async_py_in_js(f"micropip.set_constraints({constraints})")
        install_args = ""
    else:
        install_args = f"constraints={constraints}"

    if constraints and "@" not in valid_constraint:
        run_async_py_in_js(
            f"await micropip.install('pytest ==7.2.3', {install_args})",
            error_match="Can't find a pure Python 3 wheel",
        )

    run_async_py_in_js(f"await micropip.install('pytest', {install_args})")

    compare = "==" if constraints else "!="

    run_async_py_in_js(
        "import pytest",
        f"assert pytest.__version__ {compare} '7.2.2', pytest.__version__",
    )


def test_package_with_extra(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("depa")
    fake_index.add_pkg_version("depb")
    fake_index.add_pkg_version("pkga", extras={"opt_feature": ["depa"]})
    fake_index.add_pkg_version("pkgb", extras={"opt_feature": ["depb"]})

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install(["pkga[opt_feature]", "pkgb"], index_urls=[index_url])

        pkg_list = micropip.list()
        assert "pkga" in pkg_list
        assert "depa" in pkg_list
        assert "pkgb" in pkg_list
        assert "depb" not in pkg_list

    run(selenium_standalone_micropip, fake_index.url)


def test_package_with_extra_all(selenium_standalone_micropip, fake_index):
    for dep in ("depa", "depb", "depc", "depd"):
        fake_index.add_pkg_version(dep)
    fake_index.add_pkg_version("pkga", extras={"all": ["depa", "depb"]})
    fake_index.add_pkg_version(
        "pkgb", extras={"opt_feature": ["depc"], "all": ["depc", "depd"]}
    )

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install(
            ["pkga[all]", "pkgb[opt_feature]"], index_urls=[index_url]
        )

        pkg_list = micropip.list()
        assert "depa" in pkg_list
        assert "depb" in pkg_list
        assert "depc" in pkg_list
        assert "depd" not in pkg_list

    run(selenium_standalone_micropip, fake_index.url)


@pytest.mark.parametrize("transitive_req", [True, False])
def test_package_with_extra_transitive(
    selenium_standalone_micropip, fake_index, transitive_req
):
    fake_index.add_pkg_version("depb")
    pkga_optional_dep = "depa[opt_feature]" if transitive_req else "depa"
    fake_index.add_pkg_version("depa", extras={"opt_feature": ["depb"]})
    fake_index.add_pkg_version("pkga", extras={"opt_feature": [pkga_optional_dep]})

    @run_in_pyodide
    async def run(selenium, index_url, transitive_req):
        import micropip

        await micropip.install(["pkga[opt_feature]"], index_urls=[index_url])

        pkg_list = micropip.list()
        assert "depa" in pkg_list
        assert ("depb" in pkg_list) == transitive_req

    run(selenium_standalone_micropip, fake_index.url, transitive_req)


def test_install_keep_going(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy", requirements=["dep1", "dep2"])
    fake_index.add_pkg_version("dep1", tag="cp313-cp313-invalid")
    fake_index.add_pkg_version("dep2", tag="cp313-cp313-invalid")

    @run_in_pyodide
    async def run(selenium, index_url):
        import pytest

        import micropip

        # report order is non-deterministic
        with pytest.raises(ValueError, match="(dep1|dep2).*(dep2|dep1)"):
            await micropip.install("dummy", keep_going=True, index_urls=[index_url])

    run(selenium_standalone_micropip, fake_index.url)


def test_install_version_compare_prerelease(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy", "3.2.0")
    fake_index.add_pkg_version("dummy", "3.2.1a1")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("dummy==3.2.1a1", index_urls=[index_url])
        await micropip.install("dummy>=3.2.0", index_urls=[index_url])

        # Older version should not be installed
        assert micropip.list()["dummy"].version == "3.2.1a1"

    run(selenium_standalone_micropip, fake_index.url)


def test_install_no_deps(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy", requirements=["dep"])
    fake_index.add_pkg_version("dep")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("dummy", deps=False, index_urls=[index_url])

        assert "dummy" in micropip.list()
        assert "dep" not in micropip.list()

    run(selenium_standalone_micropip, fake_index.url)


@pytest.mark.parametrize("pre", [True, False])
def test_install_pre(selenium_standalone_micropip, fake_index, pre):
    version_alpha = "2.0.1a1"
    version_stable = "1.0.0"
    fake_index.add_pkg_version("dummy", version_stable)
    fake_index.add_pkg_version("dummy", version_alpha)

    @run_in_pyodide
    async def run(selenium, index_url, pre, expected):
        import micropip

        await micropip.install("dummy", pre=pre, index_urls=[index_url])
        assert micropip.list()["dummy"].version == expected

    expected = version_alpha if pre else version_stable
    run(selenium_standalone_micropip, fake_index.url, pre, expected)


def test_fetch_wheel_fail(selenium_standalone_micropip, fake_index):
    # The index serves 404 for files it doesn't know about
    url = fake_index.url.replace("/simple", "/files/xxx-1.0.0-py3-none-any.whl")

    @run_in_pyodide
    async def run(selenium, url):
        import pytest

        import micropip

        with pytest.raises(ValueError, match="Access-Control-Allow-Origin"):
            await micropip.install(url)

    run(selenium_standalone_micropip, url)


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_install_with_credentials(selenium_standalone_micropip):
    import json
    from unittest.mock import MagicMock, patch

    import micropip

    fetch_response_mock = MagicMock()

    async def myfunc():
        return json.dumps({})

    fetch_response_mock.string.side_effect = myfunc

    @patch(
        "micropip._compat._compat_in_pyodide.pyfetch", return_value=fetch_response_mock
    )
    async def call_micropip_install(pyfetch_mock):
        try:
            await micropip.install("pyodide-micropip-test", credentials="include")
        except BaseException:
            # The above will raise an exception as the mock data is garbage
            # but it is sufficient for this test
            pass

        call_args = pyfetch_mock.call_args.kwargs
        assert call_args["credentials"] == "include"

    await call_micropip_install()


def test_load_binary_wheel1(selenium_standalone_micropip, fake_index):
    selenium = selenium_standalone_micropip
    tag = selenium.run("from micropip._utils import sys_tags; str(sys_tags()[0])")
    assert "emscripten" in tag
    fake_index.add_pkg_version("dummy", tag=tag)

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("dummy", index_urls=[index_url])
        assert "dummy" in micropip.list()

    run(selenium, fake_index.url)


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_load_binary_wheel2(selenium_standalone_micropip):
    from pyodide_js._api import lockfile_packages

    import micropip

    await micropip.install(lockfile_packages.regex.file_name)
    import regex  # noqa: F401


def test_emfs(selenium_standalone_micropip, wheel_catalog):
    snowball_wheel = wheel_catalog.get("snowballstemmer")

    @run_in_pyodide()
    async def run_test(selenium, url, wheel_name):
        from pyodide.http import pyfetch

        import micropip

        resp = await pyfetch(url)
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

    run_test(selenium_standalone_micropip, snowball_wheel.url, snowball_wheel.filename)


def test_emfs_error(selenium_standalone_micropip):
    @run_in_pyodide()
    async def run_test(selenium):
        import micropip
        from micropip._utils import sys_tags

        tag = sys_tags()[0]
        wheel = f"a-2.0.2-{tag.interpreter}-{tag.abi}-{tag.platform}.whl"
        try:
            await micropip.install(f"emfs:{wheel}")
        except FileNotFoundError as e:
            assert f"No such file or directory: '{wheel}'" in str(e)
        else:
            raise AssertionError("FileNotFoundError not raised")

    run_test(selenium_standalone_micropip)


def test_logging(selenium_standalone_micropip, wheel_catalog):
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

    snowball_wheel = wheel_catalog.get("snowballstemmer")
    wheel_url = snowball_wheel.url
    name, version, _, _ = parse_wheel_filename(snowball_wheel.filename)

    run_test(selenium_standalone_micropip, wheel_url, name, version)


def test_custom_index_urls(selenium_standalone_micropip, fake_index, httpserver):
    from fake_index import FakePackageIndex

    # An index that doesn't have the package, micropip should fall back to the next one
    empty_index = FakePackageIndex(httpserver)
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_urls, wheel_url):
        import micropip

        await micropip.install("dummy", index_urls=index_urls)

        assert micropip.list()["dummy"].source.lower() == "pypi"
        assert "dummy" in micropip.freeze()
        assert wheel_url in micropip.freeze()

    run(
        selenium_standalone_micropip,
        [empty_index.url, fake_index.url],
        wheel.url,
    )


def test_install_pkg_with_sharedlib_deps(selenium_standalone_micropip, wheel_catalog):
    """
    Test if micropip can locate shared libraries in the wheel file correctly.
    shapely requires libgeos and it is bundled inside the shapely wheel.
    If micropip does not locate the shared libraries correctly,
    it will fail with the message "Didn't expect to load any more file_packager files!"

    TODO: maybe build a wheel for test-only purpose instead of relying on a real package?
    """
    selenium = selenium_standalone_micropip
    numpy_wheel = wheel_catalog.get("numpy")
    shapely_wheel = wheel_catalog.get("shapely")

    @run_in_pyodide
    async def run(selenium, numpy_url, shapely_url):
        import micropip

        await micropip.install(numpy_url)
        await micropip.install(shapely_url)

        from shapely.geometry import Point

        Point(0, 0)

    run(selenium, numpy_wheel.url, shapely_wheel.url)


def test_reinstall_different_version(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy", "1.0.0")
    fake_index.add_pkg_version("dummy", "2.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import importlib.metadata

        import pytest

        import micropip

        await micropip.install("dummy==2.0.0", index_urls=[index_url])
        assert micropip.list()["dummy"].version == "2.0.0"
        assert importlib.metadata.version("dummy") == "2.0.0"

        with pytest.raises(ValueError, match="already installed"):
            await micropip.install(
                "dummy==1.0.0", reinstall=False, index_urls=[index_url]
            )

        await micropip.install("dummy==1.0.0", reinstall=True, index_urls=[index_url])
        assert micropip.list()["dummy"].version == "1.0.0"
        assert importlib.metadata.version("dummy") == "1.0.0"

    run(selenium_standalone_micropip, fake_index.url)
