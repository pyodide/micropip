# This file contains tests that actually query remote package indexes,
# to ensure that micropip works with real-world package indexes.
# Since running these tests will send many requests to remote servers,
# these tests are disabled by default.
# To run these tests,  the --remote-url-tests option,
# Alternatively, you can run these tests in Github Actions manually.

from pytest_pyodide import run_in_pyodide

PYPI_PACKAGES = [
    "numpy",
    "black",
    "pytest",
    "snowballstemmer",
    "pytz",
    "pyodide",
    "micropip",
]

@run_in_pyodide
async def _query(selenium, index_url, header_accept, packages):
    from micropip.package_index import query_package

    for package in packages:
        project_info = await query_package(
            package,
            fetch_kwargs={"Accept": header_accept},
            index_urls=[index_url],
        )

        assert project_info.name == package

def test_pypi_json_api(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--remote-url-tests", skip=True)
    _query(
        selenium_standalone_micropip,
        index_url="https://pypi.org/pypi/{package_name}/json/",
        header_accept="application/json",
        packages=PYPI_PACKAGES,
    )
        