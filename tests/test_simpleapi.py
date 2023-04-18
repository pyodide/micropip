from pathlib import Path

import pytest

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "pypi_response"


@pytest.mark.parametrize(
    "filename, content_type, project_name",
    [
        ("pypi_response_black.json", "application/vnd.pypi.simple.v1+json", "black"),
        ("pypi_response_black.html", "text/html", "black"),
        ("pypi_response_pytest.json", "application/vnd.pypi.simple.v1+json", "pytest"),
        ("pypi_response_pytest.html", "text/html", "pytest"),
        (
            "pypi_response_snowballstemmer.json",
            "application/vnd.pypi.simple.v1+json",
            "snowballstemmer",
        ),
        ("pypi_response_snowballstemmer.html", "text/html", "snowballstemmer"),
    ],
)
def test_parse_project_details(filename, content_type, project_name):
    from micropip._simpleapi import _parse_project_details

    with open(TEST_DATA_DIR / filename) as f:
        content = f.read()

    details = _parse_project_details(content, content_type, project_name)
    keys = ["name", "meta", "files"]

    assert all(key in details for key in keys)

    assert details["name"] == project_name

    assert isinstance(details["meta"], dict)
    assert "api-version" in details["meta"]

    assert isinstance(details["files"], list)
    assert len(details["files"]) > 0

    first = details["files"][0]
    assert isinstance(first, dict)

    file_keys = ["filename", "url", "hashes"]
    assert all(key in first for key in file_keys)


# TODO: Use private PyPI server to test this
# def test_fetch_project_details():
#   pass
