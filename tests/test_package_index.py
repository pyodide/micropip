import pytest
from conftest import TEST_PYPI_RESPONSE_DIR, _read_pypi_response

import micropip._commands.index_urls as index_urls
import micropip.package_index as package_index


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_from_json(name):
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_json.json.gz"
    test_data = _read_pypi_response(test_file)

    index = package_index.ProjectInfo.from_json_api(test_data)
    assert index.name == name
    assert index.releases

    versions = list(index.releases.keys())
    assert versions
    assert versions == sorted(versions)

    for files in index.releases.values():
        for file in files:
            assert file.filename in file.url
            assert len(file.sha256) == 64


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_from_simple_json(name):
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.json.gz"
    test_data = _read_pypi_response(test_file)

    index = package_index.ProjectInfo.from_simple_json_api(test_data)
    assert index.name == name
    assert index.releases

    versions = list(index.releases.keys())
    assert versions
    assert versions == sorted(versions)

    for files in index.releases.values():
        for file in files:
            assert file.filename in file.url
            assert len(file.sha256) == 64


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_equal(name):
    # The different ways of parsing the same data should result in the same
    test_file_json = TEST_PYPI_RESPONSE_DIR / f"{name}_json.json.gz"
    test_file_simple_json = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.json.gz"

    test_data_json = _read_pypi_response(test_file_json)
    test_data_simple_json = _read_pypi_response(test_file_simple_json)

    index_json = package_index.ProjectInfo.from_json_api(test_data_json)
    index_simple_json = package_index.ProjectInfo.from_simple_json_api(
        test_data_simple_json
    )

    assert index_json.name == index_simple_json.name

    for version_json, version_simple_json in zip(
        index_json.releases, index_simple_json.releases, strict=True
    ):
        assert version_json == version_simple_json
        files_json = list(index_json.releases[version_json])
        files_simple_json = list(index_simple_json.releases[version_simple_json])

        assert len(files_json) == len(files_simple_json)
        for f_json, f_simple_json in zip(files_json, files_simple_json, strict=True):
            assert f_json.filename == f_simple_json.filename
            assert f_json.url == f_simple_json.url
            assert f_json.version == f_simple_json.version
            assert f_json.sha256 == f_simple_json.sha256


def test_set_index_urls():
    default_index_urls = package_index.DEFAULT_INDEX_URLS
    assert package_index.INDEX_URLS == default_index_urls

    valid_url1 = "https://pkg-index.com/{package_name}/json/"
    valid_url2 = "https://another-pkg-index.com/{package_name}"
    valid_url3 = "https://another-pkg-index.com/simple/"
    try:
        index_urls.set_index_urls(valid_url1)
        assert package_index.INDEX_URLS == [valid_url1]

        index_urls.set_index_urls([valid_url1, valid_url2, valid_url3])
        assert package_index.INDEX_URLS == [valid_url1, valid_url2, valid_url3]
    finally:
        index_urls.set_index_urls(default_index_urls)
        assert package_index.INDEX_URLS == default_index_urls


def test_contain_placeholder():
    assert package_index._contain_placeholder("https://pkg-index.com/{package_name}/")
    assert package_index._contain_placeholder(
        "https://pkg-index.com/{placeholder}/", placeholder="placeholder"
    )
    assert not package_index._contain_placeholder("https://pkg-index.com/")


@pytest.mark.asyncio
async def test_query_package(mock_package_index_json_api):
    mock_server_snowballstemmer = mock_package_index_json_api(pkgs=["snowballstemmer"])
    mock_server_pytest = mock_package_index_json_api(pkgs=["pytest"])

    project_info = await package_index.query_package(
        "snowballstemmer", index_urls=[mock_server_snowballstemmer]
    )

    assert project_info.name == "snowballstemmer"
    assert project_info.releases

    project_info = await package_index.query_package(
        "snowballstemmer", index_urls=mock_server_snowballstemmer
    )

    assert project_info.name == "snowballstemmer"
    assert project_info.releases

    project_info = await package_index.query_package(
        "snowballstemmer", index_urls=[mock_server_pytest, mock_server_snowballstemmer]
    )

    assert project_info.name == "snowballstemmer"
    assert project_info.releases

    with pytest.raises(ValueError, match="Can't fetch metadata"):
        await package_index.query_package(
            "snowballstemmer", index_urls=[mock_server_pytest]
        )
