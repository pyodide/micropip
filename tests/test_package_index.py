import json
from pathlib import Path

import pytest

import micropip.package_index as package_index

TEST_TEMPLATES_DIR = Path(__file__).parent / "test_data" / "pypi_response"


@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_from_json(name):
    test_file = TEST_TEMPLATES_DIR / f"{name}_json.json"
    test_data = json.loads(test_file.read_text(encoding="utf-8"))

    index = package_index.ProjectInfo.from_json_api(test_data)
    assert index.name == name
    assert index.releases

    versions = list(index.releases.keys())
    assert versions == sorted(versions)

    for files in index.releases.values():
        for file in files:
            assert file.filename in file.url
            assert len(file.sha256) == 64


@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_from_simple_json(name):
    test_file = TEST_TEMPLATES_DIR / f"{name}_simple.json"
    test_data = json.loads(test_file.read_text(encoding="utf-8"))

    index = package_index.ProjectInfo.from_simple_api(test_data)
    assert index.name == name
    assert index.releases

    versions = list(index.releases.keys())
    assert versions == sorted(versions)

    for files in index.releases.values():
        for file in files:
            assert file.filename in file.url
            assert len(file.sha256) == 64


@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_equal(name):
    # The different ways of parsing the same data should result in the same
    test_file_json = TEST_TEMPLATES_DIR / f"{name}_json.json"
    test_file_simple_json = TEST_TEMPLATES_DIR / f"{name}_simple.json"

    test_data_json = json.loads(test_file_json.read_text(encoding="utf-8"))
    test_data_simple_json = json.loads(
        test_file_simple_json.read_text(encoding="utf-8")
    )

    index_json = package_index.ProjectInfo.from_json_api(test_data_json)
    index_simple_json = package_index.ProjectInfo.from_simple_api(test_data_simple_json)

    assert index_json.name == index_simple_json.name

    for version_json, version_simple_json in zip(
        index_json.releases, index_simple_json.releases, strict=True
    ):
        files_json = index_json.releases[version_json]
        files_simple_json = index_simple_json.releases[version_simple_json]

        assert len(files_json) == len(files_simple_json)
        for f_json, f_simple_json in zip(files_json, files_simple_json, strict=True):
            assert f_json.filename == f_simple_json.filename
            assert f_json.url == f_simple_json.url
            assert f_json.version == f_simple_json.version
            assert f_json.sha256 == f_simple_json.sha256
