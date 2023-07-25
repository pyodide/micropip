# This file contains tests that actually query remote package indexes,
# to ensure that micropip works with real-world package indexes.
# Since running these tests will send many requests to remote servers,
# these tests are disabled by default.
#
# To run these tests, add `--run-remote-index-tests` flag, or
# these tests can also be run in Github Actions manually.
import functools
import random

from pytest_pyodide import run_in_pyodide


@run_in_pyodide
async def _query(selenium, index_url, header_accept, packages):
    from micropip.package_index import query_package

    for package in packages:
        await query_package(
            package,
            fetch_kwargs={"Accept": header_accept},
            index_urls=[index_url],
        )


@functools.cache
def _random_pypi_packages(k: int) -> list[str]:
    # Select random K PyPI packages
    import requests  # type: ignore[import]

    top_pypi_packages = (
        "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
    )
    packages = requests.get(top_pypi_packages).json()
    rows = packages["rows"]

    packages = random.choices(rows, k=k)
    names = [package["project"] for package in packages]
    return names


# 1) PyPI


def test_pypi_json_api(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--run-remote-index-tests", skip=True)
    PYPI_PACKAGES = _random_pypi_packages(k=10)
    _query(
        selenium_standalone_micropip,
        index_url="https://pypi.org/pypi/{package_name}/json",
        header_accept="application/json",
        packages=PYPI_PACKAGES,
    )


def test_pypi_simple_json_api(selenium_standalone_micropip, pytestconfig):
    pytestconfig.getoption("--run-remote-index-tests", skip=True)
    PYPI_PACKAGES = _random_pypi_packages(k=10)
    _query(
        selenium_standalone_micropip,
        index_url="https://pypi.org/simple",
        header_accept="application/vnd.pypi.simple.v1+json",
        packages=PYPI_PACKAGES,
    )


# As of 07/2023, some Simple HTML API responses from PyPI does not contain CORS headers

# def test_pypi_simple_html_api(selenium_standalone_micropip, pytestconfig):
#     pytestconfig.getoption("--run-remote-index-tests", skip=True)
#     PYPI_PACKAGES = _random_pypi_packages(k=5)
#     PYPI_PACKAGES=["inflection"]
#     _query(
#         selenium_standalone_micropip,
#         index_url="https://pypi.org/simple",
#         header_accept="text/html",
#         packages=PYPI_PACKAGES,
#     )

# 2) Anaconda.org
# As of 07/2023:
# - only support simple HTML API (PEP 503)
# - does not contain CORS headers in its response

# def test_anaconda_simple_html_api(selenium_standalone_micropip, pytestconfig):
#     pytestconfig.getoption("--run-remote-index-tests", skip=True)

#     # One of the indexes in anaconda.org
#     ANACONDA_INDEX_URL = "https://pypi.anaconda.org/beeware/simple"
#     ANACONDA_PACKAGES = [
#         "pynacl",
#         "bitarray",
#     ]

#     _query(
#         selenium_standalone_micropip,
#         index_url=ANACONDA_INDEX_URL,
#         header_accept="text/html",
#         packages=ANACONDA_PACKAGES,
#     )
