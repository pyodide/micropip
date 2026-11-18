from pytest_pyodide import run_in_pyodide


def test_list_pypi_package(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("dummy", index_urls=[index_url])
        pkg_list = micropip.list()
        assert "dummy" in pkg_list
        assert pkg_list["dummy"].source.lower() == "pypi"

    run(selenium_standalone_micropip, fake_index.url)


def test_list_wheel_package(selenium_standalone_micropip, fake_index):
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, wheel_url):
        import micropip

        await micropip.install(wheel_url)
        pkg_list = micropip.list()
        assert "dummy" in pkg_list
        assert pkg_list["dummy"].source.lower() == wheel_url.lower()

    run(selenium_standalone_micropip, wheel.url)


def test_list_wheel_name_mismatch(selenium_standalone_micropip, fake_index):
    wheel = fake_index.add_pkg_version("dummy-Dummy")
    assert wheel.filename == "dummy_dummy-1.0.0-py3-none-any.whl"

    @run_in_pyodide
    async def run(selenium, wheel_url):
        import micropip

        await micropip.install(wheel_url)
        pkg_list = micropip.list()
        assert "dummy-Dummy" in pkg_list
        assert pkg_list["dummy-Dummy"].source.lower() == wheel_url.lower()

    run(selenium_standalone_micropip, wheel.url)


def test_list_load_package_from_url(selenium_standalone_micropip, wheel_catalog):
    snowball_wheel = wheel_catalog.get("snowballstemmer")
    url = snowball_wheel.url

    selenium = selenium_standalone_micropip
    selenium.run_js(f"""
        await pyodide.loadPackage({url!r});
        await pyodide.runPythonAsync(`
            import micropip
            assert "snowballstemmer" in micropip.list()
        `);
        """)


def test_list_pyodide_package(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "regex"
            );
        `);
        """)
    selenium.run_js("""
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """)


def test_list_loaded_from_js(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js("""
        await pyodide.loadPackage("regex");
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """)
