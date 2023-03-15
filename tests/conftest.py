from pathlib import Path

import pytest
from pytest_pyodide import spawn_web_server


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
