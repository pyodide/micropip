import pytest
from conftest import TEST_PYPI_RESPONSE_DIR

import micropip.package_index as package_index


def _check_project_info(project_info: package_index.ProjectInfo):
    assert project_info.name
    assert project_info.releases

    versions = list(project_info.releases.keys())
    assert versions
    assert versions == sorted(versions)

    for files in project_info.releases.values():
        for file in files:
            assert file.filename in file.url
            if file.sha256 is not None:
                assert len(file.sha256) == 64
            assert file.url.startswith("https://")


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_from_json(name):
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_json.json"
    test_data = test_file.read_bytes()

    info = package_index.ProjectInfo.from_json_api(test_data)
    _check_project_info(info)


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_from_simple_json(name):
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.json"
    test_data = test_file.read_bytes()

    info = package_index.ProjectInfo.from_simple_json_api(test_data)
    _check_project_info(info)


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_from_simple_html(name):
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.html"
    test_data = test_file.read_bytes()

    info = package_index.ProjectInfo.from_simple_html_api(
        test_data.decode("utf-8"), name, index_base_url="https://files.pythonhosted.org"
    )
    _check_project_info(info)


@pytest.mark.parametrize("name", ["black"])
def test_project_info_no_base_from_simple_html(name):
    """
    This test that the black_simple.html.gz does not have
    absolute url, we test that if we don't pass the https:// domain,
    t_check_project_info will indeed fail.
    """
    test_file = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.html"
    test_data = test_file.read_bytes()

    info = package_index.ProjectInfo.from_simple_html_api(
        test_data.decode("utf-8"), name, index_base_url="no_base"
    )
    with pytest.raises(AssertionError):
        _check_project_info(info)


@pytest.mark.parametrize(
    "name", ["numpy", "black", "pytest", "snowballstemmer", "pytz"]
)
def test_project_info_equal(name):
    # The different ways of parsing the same data should result in the same
    # Simple HTML API does not contain `versions` key, so it is not easy to compare...
    test_file_json = TEST_PYPI_RESPONSE_DIR / f"{name}_json.json"
    test_file_simple_json = TEST_PYPI_RESPONSE_DIR / f"{name}_simple.json"

    test_data_json = test_file_json.read_bytes()
    test_data_simple_json = test_file_simple_json.read_bytes()

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


def test_contain_placeholder():
    assert package_index._contain_placeholder("https://pkg-index.com/{package_name}/")
    assert package_index._contain_placeholder(
        "https://pkg-index.com/{placeholder}/", placeholder="placeholder"
    )
    assert not package_index._contain_placeholder("https://pkg-index.com/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_fixture",
    (
        "mock_package_index_json_api",
        "mock_package_index_simple_json_api",
        "mock_package_index_simple_html_api",
    ),
)
@pytest.mark.parametrize(
    "pkg1, pkg2",
    [
        ("snowballstemmer", "pytest"),
        ("pytest", "snowballstemmer"),
        ("black", "pytest"),
        ("numpy", "black"),
    ],
)
async def test_query_package(mock_fixture, pkg1, pkg2, request):
    gen_mock_server = request.getfixturevalue(mock_fixture)
    pkg1_index_url = gen_mock_server(pkgs=[pkg1], pkgs_not_found=[pkg2])
    pkg2_index_url = gen_mock_server(pkgs=[pkg2], pkgs_not_found=[pkg1])

    for _index_urls in (
        pkg1_index_url,
        [pkg1_index_url],
        [pkg2_index_url, pkg1_index_url],
    ):
        project_info = await package_index.query_package(pkg1, index_urls=_index_urls)

        assert project_info.name == pkg1
        assert project_info.releases

    with pytest.raises(ValueError, match="Can't fetch metadata"):
        await package_index.query_package(pkg1, index_urls=[pkg2_index_url])
