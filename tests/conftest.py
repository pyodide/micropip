import functools
import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from pytest_httpserver import HTTPServer
from pytest_pyodide.runner import JavascriptException

from micropip._vendored.packaging.src.packaging.utils import parse_wheel_filename


def pytest_addoption(parser):
    parser.addoption(
        "--run-remote-index-tests",
        action="store_true",
        default=None,
        help="Run tests that query remote package indexes.",
    )

    parser.addoption(
        "--integration",
        action="store_true",
        default=None,
        help="Run integration tests.",
    )


TEST_PYPI_RESPONSE_DIR = Path(__file__).parent / "test_data" / "pypi_response"
TEST_WHEEL_DIR = Path(__file__).parent / "test_data" / "wheel"
SNOWBALL_WHEEL = "snowballstemmer-2.0.0-py2.py3-none-any.whl"
PYTEST_WHEEL = "pytest-7.2.2-py3-none-any.whl"


def _read_gzipped_testfile(file: Path) -> bytes:
    return gzip.decompress(file.read_bytes())


def _build(build_dir, dist_dir):
    import build
    from build.env import DefaultIsolatedEnv

    with DefaultIsolatedEnv() as env:
        # https://build.pypa.io/en/stable/api.html#build.ProjectBuilder
        builder = build.ProjectBuilder(
            source_dir=build_dir,
            python_executable=env.python_executable,
        )

        env.install(builder.build_system_requires)
        builder.build("wheel", output_directory=dist_dir)


@pytest.fixture(scope="session")
def wheel_path(tmp_path_factory):
    # Build a micropip wheel for testing
    output_dir = tmp_path_factory.mktemp("wheel")

    _build(Path(__file__).parent.parent, output_dir)

    yield output_dir


@pytest.fixture
def selenium_standalone_micropip(selenium_standalone, wheel_path):
    """Import micropip before entering test so that global initialization of
    micropip doesn't count towards hiwire refcount.
    """

    wheel_dir = Path(wheel_path)
    wheel_files = list(wheel_dir.glob("*.whl"))

    if not wheel_files:
        pytest.exit("No wheel files found in wheel/ directory")

    wheel_file = wheel_files[0]

    httpserver = HTTPServer()
    httpserver.expect_request(f"/{wheel_file.name}").respond_with_data(
        wheel_file.read_bytes(),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
    )

    with httpserver:
        url = httpserver.url_for(f"/{wheel_file.name}")
        selenium_standalone.run_js(f"""
            await pyodide.loadPackage("{url}");
            pyodide.runPython("import micropip");
            """)

    yield selenium_standalone


class WheelCatalog:
    """
    A catalog of wheels for testing.
    """

    @dataclass
    class Wheel:
        _path: Path

        name: str
        version: str
        filename: str
        top_level: str
        url: str

        @property
        def content(self) -> bytes:
            return self._path.read_bytes()

    def __init__(self):
        self._wheels = {}

        self._httpserver = HTTPServer()
        self._httpserver.no_handler_status_code = 404

    def __enter__(self):
        self._httpserver.__enter__()
        return self

    def __exit__(self, *args: Any):
        self._httpserver.__exit__(*args)

    def _register_handler(self, endpoint: str, data: bytes) -> str:
        self._httpserver.expect_request(f"/{endpoint}").respond_with_data(
            data,
            content_type="application/zip",
            headers={"Access-Control-Allow-Origin": "*"},
        )

        return self._httpserver.url_for(f"/{endpoint}")

    def add_wheel(self, path: Path, replace: bool = True):
        name, version = parse_wheel_filename(path.name)[0:2]
        url = self._register_handler(path.name, path.read_bytes())

        metadata_file_endpoint = path.with_suffix(".whl.metadata")
        if metadata_file_endpoint.exists():
            self._register_handler(
                metadata_file_endpoint.name, metadata_file_endpoint.read_bytes()
            )

        if name in self._wheels and not replace:
            return

        self._wheels[name] = self.Wheel(
            path, name, str(version), path.name, name.replace("-", "_"), url
        )

    def get(self, name: str) -> Wheel:
        return self._wheels[name]


@pytest.fixture(scope="session")
def wheel_catalog(pytestconfig):
    """Run a mock server that serves pre-built wheels"""
    with WheelCatalog() as catalog:
        for wheel in TEST_WHEEL_DIR.glob("*.whl"):
            catalog.add_wheel(wheel)

        # Add wheels in the pyodide distribution so we can use it in the test.
        # This is a workaround to get a wheel build with a same emscripten version that the Pyodide is build with,
        # But probably we should find a better way that does not depend on Pyodide distribution.
        dist_dir = Path(pytestconfig.getoption("dist_dir"))
        for wheel in dist_dir.glob("*.whl"):
            catalog.add_wheel(wheel, replace=False)

        yield catalog


@pytest.fixture
def fake_index(httpserver):
    """
    A package index that serves wheels built on the fly over HTTP.

    It works from inside Pyodide, so tests can run micropip end-to-end
    without monkeypatching it.
    See ``tests/fake_index.py`` for details.
    """
    from fake_index import FakePackageIndex

    return FakePackageIndex(httpserver)


def _mock_package_index_gen(
    httpserver,
    pkgs=("black", "pytest", "numpy", "pytz", "snowballstemmer"),
    pkgs_not_found=(),
    content_type="application/json",
    suffix="_json.json",
):
    # Run a mock server that serves as a package index
    import secrets

    base = secrets.token_hex(16)

    for pkg in pkgs:
        data = (TEST_PYPI_RESPONSE_DIR / f"{pkg}{suffix}").read_bytes()
        httpserver.expect_request(f"/{base}/{pkg}/").respond_with_data(
            data,
            content_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    for pkg in pkgs_not_found:
        httpserver.expect_request(f"/{base}/{pkg}/").respond_with_data(
            "Not found", status=404, content_type="text/plain"
        )

    index_url = httpserver.url_for(base)

    return index_url


@pytest.fixture
def mock_package_index_json_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_json.json",
        content_type="application/json",
    )


@pytest.fixture
def mock_package_index_simple_json_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_simple.json",
        content_type="application/vnd.pypi.simple.v1+json",
    )


@pytest.fixture
def mock_package_index_simple_html_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_simple.html",
        content_type="text/html",
    )


@pytest.fixture(
    params=[
        None,
        "pytest ==7.2.2",
        "pytest >=7.2.1,<7.2.3",
        "pytest @ {url}",
        "pytest @ emfs:{wheel}",
    ]
)
def valid_constraint(request, wheel_catalog):
    wheel = wheel_catalog.get("pytest")
    if not request.param:
        return request.param
    return request.param.format(url=wheel.url, wheel=wheel.url.split("/")[-1])


INVALID_CONSTRAINT_MESSAGES = {
    "": "parse",
    "http://example.com": "name",
    "a-package[with-extra]": "[extras]",
    "a-package": "no version or URL",
}


@pytest.fixture(params=[*INVALID_CONSTRAINT_MESSAGES.keys()])
def invalid_constraint(request):
    return request.param


@pytest.fixture
def run_async_py_in_js(selenium_standalone_micropip):
    def _run(*lines, error_match=None):
        js = "\n".join(["await pyodide.runPythonAsync(`", *lines, "`);"])
        if error_match:
            with pytest.raises(JavascriptException, match=error_match):
                selenium_standalone_micropip.run_js(js)
        else:
            selenium_standalone_micropip.run_js(js)

    return _run


@pytest.fixture
def host_compat_layer():
    """
    Fixture to provide the compatibility layer for the host environment.
    """
    from micropip._compat._compat_not_in_pyodide import CompatibilityNotInPyodide

    yield CompatibilityNotInPyodide


@pytest.fixture
def host_package_manager(host_compat_layer):
    """
    Fixture to provide a package manager for the host environment.
    """
    from micropip.package_manager import PackageManager

    package_manager = PackageManager(compat=host_compat_layer)

    yield package_manager
