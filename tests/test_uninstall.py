# isort: skip_file

import pytest
from pytest_pyodide import run_in_pyodide, spawn_web_server

TEST_PACKAGE_NAME = "test_wheel_uninstall"


@pytest.fixture(scope="module")
def test_wheel_url(test_wheel_path):

    wheel_file = next(test_wheel_path.glob(f"{TEST_PACKAGE_NAME}-*.whl")).name

    with spawn_web_server(test_wheel_path) as server:
        server_hostname, server_port, _ = server
        yield f"http://{server_hostname}:{server_port}/{wheel_file}"


def test_basic(selenium_standalone_micropip, test_wheel_url):
    @run_in_pyodide()
    async def run(selenium, pkg_name, wheel_url):
        import importlib.metadata
        import sys

        import micropip

        await micropip.install(wheel_url)

        assert pkg_name in micropip.list()
        assert pkg_name not in sys.modules

        __import__(pkg_name)
        assert pkg_name in sys.modules

        micropip.uninstall(pkg_name)
        del sys.modules[pkg_name]

        # 1. Check that the module is not available with import statement
        try:
            __import__(pkg_name)
        except ImportError:
            pass
        else:
            raise AssertionError(f"{pkg_name} should not be available")

        # 2. Check that the module is not available with importlib.metadata
        for dist in importlib.metadata.distributions():
            if dist.name == pkg_name:
                raise AssertionError(f"{pkg_name} should not be available")

        # 3. Check that the module is not available with micropip.list()
        assert pkg_name not in micropip.list()

    run(selenium_standalone_micropip, TEST_PACKAGE_NAME, test_wheel_url)


def test_files(selenium_standalone_micropip, test_wheel_url):
    """
    Check all files are removed after uninstallation.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, wheel_url):
        import importlib.metadata

        import micropip

        await micropip.install(wheel_url)
        assert pkg_name in micropip.list()

        dist = importlib.metadata.distribution(pkg_name)
        files = dist.files

        for file in files:
            assert file.locate().is_file(), f"{file.locate()} is not a file"

        assert dist._path.is_dir(), f"{dist._path} is not a directory"

        micropip.uninstall(pkg_name)

        for file in files:
            assert (
                not file.locate().is_file()
            ), f"{file.locate()} still exists after removal"

        assert not dist._path.is_dir(), f"{dist._path} still exists after removal"

    run(selenium_standalone_micropip, TEST_PACKAGE_NAME, test_wheel_url)


def test_install_again(selenium_standalone_micropip, test_wheel_url):
    """
    Check that uninstalling and installing again works.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, wheel_url):
        import sys

        import micropip

        await micropip.install(wheel_url)

        assert pkg_name in micropip.list()

        __import__(pkg_name)

        micropip.uninstall(pkg_name)

        assert pkg_name not in micropip.list()

        del sys.modules[pkg_name]

        try:
            __import__(pkg_name)
        except ImportError:
            pass
        else:
            raise AssertionError(f"{pkg_name} should not be available")

        await micropip.install(wheel_url)

        assert pkg_name in micropip.list()
        __import__(pkg_name)

    run(selenium_standalone_micropip, TEST_PACKAGE_NAME, test_wheel_url)


def test_warning_not_installed(selenium_standalone_micropip):
    """
    Test warning when trying to uninstall a package that is not installed.
    """

    @run_in_pyodide()
    async def run(selenium):
        import micropip
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            micropip.uninstall("no-such-package")

            assert len(w) == 1
            assert "not installed" in str(w[-1].message)

    run(selenium_standalone_micropip)


def test_warning_file_removed(selenium_standalone_micropip, test_wheel_url):
    """
    Test warning when files in a package are removed by user.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, wheel_url):
        from importlib.metadata import distribution
        import micropip

        await micropip.install(wheel_url)

        assert pkg_name in micropip.list()

        dist = distribution(pkg_name)
        files = dist.files
        file1 = files[0]
        file2 = files[1]

        file1.locate().unlink()
        file2.locate().unlink()

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            micropip.uninstall(pkg_name)

            assert len(w) == 2
            assert "does not exist" in str(w[-1].message)
            assert "does not exist" in str(w[-2].message)

    run(selenium_standalone_micropip, TEST_PACKAGE_NAME, test_wheel_url)


def test_warning_remaining_file(selenium_standalone_micropip, test_wheel_url):
    """
    Test warning when there are remaining files after uninstallation.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, wheel_url):
        from importlib.metadata import distribution
        import micropip

        await micropip.install(wheel_url)
        assert pkg_name in micropip.list()

        pkg_dir = distribution(pkg_name)._path.parent / "deep"
        (pkg_dir / "extra-file.txt").touch()

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            micropip.uninstall(pkg_name)

            assert len(w) == 1
            assert "is not empty after uninstallation" in str(w[-1].message)

    run(selenium_standalone_micropip, TEST_PACKAGE_NAME, test_wheel_url)


def test_pyodide_repodata(selenium_standalone_micropip):
    """
    Test micropip.uninstall handles packages in repodata.json
    """

    @run_in_pyodide()
    async def run(selenium):
        import micropip
        import pyodide_js

        await pyodide_js.loadPackage("pytest")
        micropip.uninstall("pytest")
        assert "pytest" not in micropip.list()

        try:
            __import__("pytest")
        except ImportError:
            pass
        else:
            raise AssertionError("pytest should not be available")

        await pyodide_js.loadPackage("pytest")
        assert "pytest" in micropip.list()

        __import__("pytest")

    run(selenium_standalone_micropip)
