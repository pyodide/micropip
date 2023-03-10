from pathlib import Path

import pytest
from pytest_pyodide import spawn_web_server


@pytest.fixture(scope="module")
def wheel_path(tmp_path_factory):
    # Build a micropip wheel for testing
    import build
    from build.env import IsolatedEnvBuilder

    output_dir = tmp_path_factory.mktemp("wheel")

    with IsolatedEnvBuilder() as env:
        builder = build.ProjectBuilder(Path(__file__).parent.parent)
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        env.install(builder.build_system_requires)
        builder.build("wheel", output_directory=output_dir)

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


@pytest.fixture(scope="module")
def wheel_server_url():
    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server

        base_url = f"http://{server_hostname}:{server_port}/"

        yield base_url
