# isort: skip_file

from pytest_pyodide import run_in_pyodide
from packaging.utils import parse_wheel_filename

TEST_PACKAGE_NAME = "test_wheel_uninstall"


def test_basic(selenium_standalone_micropip, test_wheel_catalog):
    @run_in_pyodide()
    async def run(selenium, pkg_name, pkg_name_normalized, wheel_url):
        import importlib.metadata
        import sys

        import micropip

        await micropip.install(wheel_url)

        assert pkg_name_normalized in micropip.list()
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

    test_wheel = test_wheel_catalog.get(TEST_PACKAGE_NAME)

    run(
        selenium_standalone_micropip,
        test_wheel.name,
        test_wheel.normalized_name,
        test_wheel.url,
    )


def test_files(selenium_standalone_micropip, test_wheel_catalog):
    """
    Check all files are removed after uninstallation.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, pkg_name_normalized, wheel_url):
        import importlib.metadata

        import micropip

        await micropip.install(wheel_url)
        assert pkg_name_normalized in micropip.list()

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

    test_wheel = test_wheel_catalog.get(TEST_PACKAGE_NAME)

    run(
        selenium_standalone_micropip,
        test_wheel.name,
        test_wheel.normalized_name,
        test_wheel.url,
    )


def test_install_again(selenium_standalone_micropip, test_wheel_catalog):
    """
    Check that uninstalling and installing again works.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, pkg_name_normalized, wheel_url):
        import sys

        import micropip

        await micropip.install(wheel_url)

        assert pkg_name_normalized in micropip.list()

        __import__(pkg_name)

        micropip.uninstall(pkg_name)

        assert pkg_name_normalized not in micropip.list()

        del sys.modules[pkg_name]

        try:
            __import__(pkg_name)
        except ImportError:
            pass
        else:
            raise AssertionError(f"{pkg_name} should not be available")

        await micropip.install(wheel_url)

        assert pkg_name_normalized in micropip.list()
        __import__(pkg_name)

    test_wheel = test_wheel_catalog.get(TEST_PACKAGE_NAME)

    run(
        selenium_standalone_micropip,
        test_wheel.name,
        test_wheel.normalized_name,
        test_wheel.url,
    )


def test_warning_not_installed(selenium_standalone_micropip):
    """
    Test warning when trying to uninstall a package that is not installed.
    """

    @run_in_pyodide()
    async def run(selenium):
        import micropip

        import contextlib
        import io

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            micropip.uninstall("no-such-package")

            captured = buf.getvalue()
            logs = captured.strip().split("\n")
            assert len(logs) == 1
            assert "Skipping 'no-such-package' as it is not installed." in logs[0]

    run(selenium_standalone_micropip)


def test_warning_file_removed(selenium_standalone_micropip, test_wheel_catalog):
    """
    Test warning when files in a package are removed by user.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, pkg_name_normalized, wheel_url):
        from importlib.metadata import distribution
        import micropip
        import contextlib
        import io

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            await micropip.install(wheel_url)

            assert pkg_name_normalized in micropip.list()

            dist = distribution(pkg_name_normalized)
            files = dist.files
            file1 = files[0]
            file2 = files[1]

            file1.locate().unlink()
            file2.locate().unlink()

            micropip.uninstall(pkg_name_normalized)

            captured = buf.getvalue()
            logs = captured.strip().split("\n")

            assert len(logs) == 2
            assert "does not exist" in logs[-1]
            assert "does not exist" in logs[-2]

    test_wheel = test_wheel_catalog.get(TEST_PACKAGE_NAME)

    run(
        selenium_standalone_micropip,
        test_wheel.name,
        test_wheel.normalized_name,
        test_wheel.url,
    )


def test_warning_remaining_file(selenium_standalone_micropip, test_wheel_catalog):
    """
    Test warning when there are remaining files after uninstallation.
    """

    @run_in_pyodide()
    async def run(selenium, pkg_name, pkg_name_normalized, wheel_url):
        from importlib.metadata import distribution
        import micropip
        import contextlib
        import io

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            await micropip.install(wheel_url)
            assert pkg_name_normalized in micropip.list()

            pkg_dir = distribution(pkg_name_normalized)._path.parent / "deep"
            (pkg_dir / "extra-file.txt").touch()

            micropip.uninstall(pkg_name_normalized)

            captured = buf.getvalue()
            logs = captured.strip().split("\n")

            assert len(logs) == 1
            assert "is not empty after uninstallation" in logs[0]

    test_wheel = test_wheel_catalog.get(TEST_PACKAGE_NAME)

    run(
        selenium_standalone_micropip,
        test_wheel.name,
        test_wheel.normalized_name,
        test_wheel.url,
    )


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


def test_logging(selenium_standalone_micropip, test_wheel_catalog):
    snowballstemmer_wheel = test_wheel_catalog.get("snowballstemmer")
    wheel_url = snowballstemmer_wheel.url
    name, version, _, _ = parse_wheel_filename(snowballstemmer_wheel.filename)

    @run_in_pyodide(packages=["micropip"])
    async def run_test(selenium, url, name, version):
        import micropip
        import contextlib
        import io

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            await micropip.install(url)
            micropip.uninstall("snowballstemmer", verbose=True)

            captured = buf.getvalue()

            assert f"Found existing installation: {name} {version}" in captured
            assert f"Successfully uninstalled {name}-{version}" in captured

    run_test(selenium_standalone_micropip, wheel_url, name, version)
