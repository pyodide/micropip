import functools
import gzip
import io
import sys
import zipfile
from importlib.metadata import Distribution, PackageNotFoundError
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pytest_pyodide import spawn_web_server


def pytest_addoption(parser):
    parser.addoption(
        "--run-remote-index-tests",
        action="store_true",
        default=None,
        help="Run tests that query remote package indexes.",
    )


SNOWBALL_WHEEL = "snowballstemmer-2.0.0-py2.py3-none-any.whl"

EMSCRIPTEN_VER = "3.1.14"
PLATFORM = f"emscripten_{EMSCRIPTEN_VER.replace('.', '_')}_wasm32"
CPVER = f"cp{sys.version_info.major}{sys.version_info.minor}"

TEST_PYPI_RESPONSE_DIR = Path(__file__).parent / "test_data" / "pypi_response"


def _read_pypi_response(file: Path) -> bytes:
    return gzip.decompress(file.read_bytes())


def _build(build_dir, dist_dir):
    import build
    from build.env import IsolatedEnvBuilder

    with IsolatedEnvBuilder() as env:
        builder = build.ProjectBuilder(build_dir)
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        env.install(builder.build_system_requires)
        builder.build("wheel", output_directory=dist_dir)


@pytest.fixture(scope="session")
def wheel_path(tmp_path_factory):
    # Build a micropip wheel for testing
    output_dir = tmp_path_factory.mktemp("wheel")

    _build(Path(__file__).parent.parent, output_dir)

    yield output_dir


@pytest.fixture(scope="session")
def test_wheel_path(tmp_path_factory):
    # Build a test wheel for testing
    output_dir = tmp_path_factory.mktemp("wheel")

    _build(Path(__file__).parent / "test_data" / "test_wheel_uninstall", output_dir)

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
    with spawn_web_server(wheel_dir) as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        selenium_standalone.run_js(
            f"""
            await pyodide.loadPackage("{base_url + wheel_file.name}");
            await pyodide.loadPackage(["packaging"]);
            pyodide.runPython("import micropip");
            """
        )

    yield selenium_standalone


@pytest.fixture
def mock_platform(monkeypatch):
    monkeypatch.setenv("_PYTHON_HOST_PLATFORM", PLATFORM)
    from micropip import _utils

    _utils.sys_tags.cache_clear()
    monkeypatch.setattr(_utils, "get_platform", lambda: PLATFORM)


@pytest.fixture
def wheel_base(monkeypatch):
    with TemporaryDirectory() as tmpdirname:
        WHEEL_BASE = Path(tmpdirname).absolute()
        import site

        monkeypatch.setattr(
            site, "getsitepackages", lambda: [WHEEL_BASE], raising=False
        )
        yield WHEEL_BASE


@pytest.fixture
def mock_importlib(monkeypatch, wheel_base):
    import importlib.metadata

    def _mock_importlib_from_name(name: str) -> Distribution:
        dists = _mock_importlib_distributions()
        for dist in dists:
            if dist.name == name:
                return dist
        raise PackageNotFoundError(name)

    def _mock_importlib_version(name: str) -> str:
        dists = _mock_importlib_distributions()
        for dist in dists:
            if dist.name == name:
                return dist.version
        raise PackageNotFoundError(name)

    def _mock_importlib_distributions():
        return (Distribution.at(p) for p in wheel_base.glob("*.dist-info"))  # type: ignore[union-attr]

    monkeypatch.setattr(importlib.metadata, "version", _mock_importlib_version)
    monkeypatch.setattr(
        importlib.metadata, "distributions", _mock_importlib_distributions
    )
    monkeypatch.setattr(
        importlib.metadata.Distribution, "from_name", _mock_importlib_from_name
    )


class Wildcard:
    def __eq__(self, other):
        return True


class mock_fetch_cls:
    def __init__(self):
        self.releases_map = {}
        self.metadata_map = {}
        self.top_level_map = {}

    def _make_wheel_filename(
        self, name: str, version: str, platform: str = "generic"
    ) -> str:
        if platform == "generic":
            platform_str = "py3-none-any"
        elif platform == "emscripten":
            platform_str = f"{CPVER}-{CPVER}-{PLATFORM}"
        elif platform == "linux":
            platform_str = f"{CPVER}-{CPVER}-manylinux_2_31_x86_64"
        elif platform == "windows":
            platform_str = f"{CPVER}-{CPVER}-win_amd64"
        elif platform == "invalid":
            platform_str = f"{CPVER}-{CPVER}-invalid"
        else:
            platform_str = platform

        return f"{name.replace('-', '_').lower()}-{version}-{platform_str}.whl"

    def __eq__(self, other):
        return True

    def add_pkg_version(
        self,
        name: str,
        version: str = "1.0.0",
        *,
        requirements: list[str] | None = None,
        extras: dict[str, list[str]] | None = None,
        platform: str = "generic",
        top_level: list[str] | None = None,
    ) -> None:
        if requirements is None:
            requirements = []
        if extras is None:
            extras = {}
        if top_level is None:
            top_level = []
        if name not in self.releases_map:
            self.releases_map[name] = {"releases": {}}
        releases = self.releases_map[name]["releases"]
        filename = self._make_wheel_filename(name, version, platform)
        releases[version] = [
            {
                "filename": filename,
                "url": filename,
                "digests": {
                    "sha256": Wildcard(),
                },
            }
        ]
        metadata = [("Name", name), ("Version", version)] + [
            ("Requires-Dist", req) for req in requirements
        ]
        for extra, reqs in extras.items():
            metadata += [("Provides-Extra", extra)] + [
                ("Requires-Dist", f"{req}; extra == {extra!r}") for req in reqs
            ]
        self.metadata_map[filename] = metadata
        self.top_level_map[filename] = top_level

    async def query_package(self, pkgname, kwargs, index_urls=None):
        from micropip.package_index import ProjectInfo

        try:
            return ProjectInfo.from_json_api(self.releases_map[pkgname])
        except KeyError as e:
            raise ValueError(
                f"Can't fetch metadata for '{pkgname}' from PyPI. "
                "Please make sure you have entered a correct package name."
            ) from e

    async def _fetch_bytes(self, url, kwargs):
        from micropip.transaction import WheelInfo

        wheel_info = WheelInfo.from_url(url)
        version = wheel_info.version
        name = wheel_info.name
        filename = wheel_info.filename
        metadata = self.metadata_map[filename]
        metadata_str = "\n".join(": ".join(x) for x in metadata)
        toplevel = self.top_level_map[filename]
        toplevel_str = "\n".join(toplevel)

        metadata_dir = f"{name}-{version}.dist-info"

        tmp = io.BytesIO()
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:

            def write_file(filename, contents):
                archive.writestr(f"{metadata_dir}/{filename}", contents)

            write_file("METADATA", metadata_str)
            write_file("WHEEL", "Wheel-Version: 1.0")
            write_file("top_level.txt", toplevel_str)

        tmp.seek(0)

        return tmp


@pytest.fixture
def mock_fetch(monkeypatch, mock_importlib):
    pytest.importorskip("packaging")
    from micropip import package_index, transaction

    result = mock_fetch_cls()
    monkeypatch.setattr(package_index, "query_package", result.query_package)
    monkeypatch.setattr(transaction, "fetch_bytes", result._fetch_bytes)
    return result


def _mock_package_index_gen(
    httpserver,
    pkgs=("black", "pytest", "numpy", "pytz", "snowballstemmer"),
    content_type="application/json",
    suffix="_json.json.gz",
):
    # Run a mock server that serves as a package index
    import secrets

    base = secrets.token_hex(16)

    for pkg in pkgs:
        data = _read_pypi_response(TEST_PYPI_RESPONSE_DIR / f"{pkg}{suffix}")
        httpserver.expect_request(f"/{base}/{pkg}/").respond_with_data(
            data,
            content_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    index_url = httpserver.url_for(base)

    return index_url


@pytest.fixture
def mock_package_index_json_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_json.json.gz",
        content_type="application/json",
    )


@pytest.fixture
def mock_package_index_simple_json_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_simple.json.gz",
        content_type="application/vnd.pypi.simple.v1+json",
    )


@pytest.fixture
def mock_package_index_simple_html_api(httpserver):
    return functools.partial(
        _mock_package_index_gen,
        httpserver=httpserver,
        suffix="_simple.html.gz",
        content_type="text/html",
    )
