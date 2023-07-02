import json
from pathlib import Path

import pytest

import micropip.repository as repository

TEST_TEMPLATES_DIR = Path(__file__).parent / "test_data" / "pypi_response"

@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_from_json(name):
    test_file = TEST_TEMPLATES_DIR / f"{name}_json.json"
    test_data = json.loads(test_file.read_text())

    index = repository.ProjectInfo.from_json_api(test_data)
    assert index.name == name
    assert index.versions is not None
    assert index.files

    for file in index.files:
        assert file.version in index.versions
        assert file.filename in file.url
        assert len(file.sha256) == 64


@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_from_simple_json(name):
    test_file = TEST_TEMPLATES_DIR / f"{name}_simple.json"
    test_data = json.loads(test_file.read_text())

    index = repository.ProjectInfo.from_simple_api(test_data)
    assert index.name == name
    assert index.versions is not None
    assert index.files

    for file in index.files:
        assert file.version in index.versions
        assert file.filename in file.url
        assert len(file.sha256) == 64


@pytest.mark.parametrize("name", ["black", "pytest", "snowballstemmer"])
def test_project_info_equality(name):
    # The different ways of parsing the same data should result in the same
    test_file_json = TEST_TEMPLATES_DIR / f"{name}_json.json"
    test_file_simple_json = TEST_TEMPLATES_DIR / f"{name}_simple.json"

    test_data_json = json.loads(test_file_json.read_text())
    test_data_simple_json = json.loads(test_file_simple_json.read_text())

    index_json = repository.ProjectInfo.from_json_api(test_data_json)
    index_simple_json = repository.ProjectInfo.from_simple_api(test_data_simple_json)

    assert index_json.name == index_simple_json.name
    assert index_json.versions == index_simple_json.versions

    for f_json, f_simple_json in zip(
        index_json.files, index_simple_json.files, strict=True
    ):
        assert f_json.filename == f_simple_json.filename
        assert f_json.url == f_simple_json.url
        assert f_json.version == f_simple_json.version
        assert f_json.sha256 == f_simple_json.sha256
        assert f_json.size == f_simple_json.size
