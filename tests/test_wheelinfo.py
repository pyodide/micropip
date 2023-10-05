from packaging.utils import parse_wheel_filename
import pytest
from conftest import PYTEST_WHEEL, TEST_WHEEL_DIR, _read_gzipped_testfile

from micropip.wheelinfo import WheelInfo


@pytest.fixture
def dummy_wheel():
    yield WheelInfo.from_url(f"https://test.com/{PYTEST_WHEEL}")


@pytest.fixture
def dummy_wheel_content():
    yield (TEST_WHEEL_DIR / PYTEST_WHEEL).read_bytes()


@pytest.fixture
def dummy_wheel_url(httpserver):
    httpserver.expect_request(f"/{PYTEST_WHEEL}").respond_with_data(
        (TEST_WHEEL_DIR / PYTEST_WHEEL).read_bytes(),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
    )
    httpserver.expect_request(f"/{PYTEST_WHEEL}.metadata").respond_with_data(
        _read_gzipped_testfile(TEST_WHEEL_DIR / f"{PYTEST_WHEEL}.metadata.gz"),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
    )
    return httpserver.url_for(f"/{PYTEST_WHEEL}")


def test_from_url():
    url = "https://test.com/dummy_module-0.0.1-py3-none-any.whl"
    wheel = WheelInfo.from_url(url)

    assert wheel.name == "dummy-module"
    assert str(wheel.version) == "0.0.1"
    assert wheel.url == url
    assert wheel.filename == "dummy_module-0.0.1-py3-none-any.whl"
    assert wheel.size is None
    assert wheel.sha256 is None


def test_from_package_index():
    name = "dummy-module"
    filename = "dummy_module-0.0.1-py3-none-any.whl"
    url = "https://test.com/dummy_module-0.0.1-py3-none-any.whl"
    version = "0.0.1"
    sha256 = "dummy-sha256"
    size = 1234

    wheel = WheelInfo.from_package_index(name, filename, url, version, sha256, size)

    assert wheel.name == name
    assert str(wheel.version) == version
    assert wheel.url == url
    assert wheel.filename == filename
    assert wheel.size == size
    assert wheel.sha256 == sha256


def test_extract(dummy_wheel, dummy_wheel_content, tmp_path):
    dummy_wheel._data = dummy_wheel_content
    dummy_wheel._extract(tmp_path)

    assert dummy_wheel._dist_info is not None
    assert dummy_wheel._dist_info.is_dir()


def test_set_installer(dummy_wheel, dummy_wheel_content, tmp_path):
    dummy_wheel._data = dummy_wheel_content
    dummy_wheel._extract(tmp_path)

    dummy_wheel._set_installer()

    assert (dummy_wheel._dist_info / "INSTALLER").read_text() == "micropip"
    assert (dummy_wheel._dist_info / "PYODIDE_SOURCE").read_text() == dummy_wheel.url
    assert (dummy_wheel._dist_info / "PYODIDE_URL").read_text() == dummy_wheel.url
    assert (dummy_wheel._dist_info / "PYODIDE_SHA256").exists()


def test_install():
    pass


@pytest.mark.asyncio
async def test_download(dummy_wheel_url):
    wheel = WheelInfo.from_url(dummy_wheel_url)

    assert wheel._metadata is None

    await wheel.download({})

    assert wheel._metadata is not None


@pytest.mark.asyncio
async def test_requires(dummy_wheel_url, tmp_path):
    wheel = WheelInfo.from_url(dummy_wheel_url)
    await wheel.download({})

    wheel._extract(tmp_path)

    requirements_default = [str(r.name) for r in wheel.requires(set())]
    assert "pluggy" in requirements_default
    assert "hypothesis" not in requirements_default

    requirements_extra_testing = [str(r.name) for r in wheel.requires({"testing"})]
    assert "pluggy" in requirements_extra_testing
    assert "hypothesis" in requirements_extra_testing


def test_pep658_metadata_available():
    name = "dummy-module"
    filename = "dummy_module-0.0.1-py3-none-any.whl"
    url = "https://test.com/dummy_module-0.0.1-py3-none-any.whl"
    version = "0.0.1"
    sha256 = "dummy-sha256"
    size = 1234

    wheel = WheelInfo.from_package_index(name, filename, url, version, sha256, size, data_dist_info_metadata=True)
    assert wheel.pep658_metadata_available()

    wheel = WheelInfo.from_package_index(name, filename, url, version, sha256, size, data_dist_info_metadata={"sha256": "dummy-sha256"})
    assert wheel.pep658_metadata_available()

    wheel = WheelInfo.from_url(url)
    assert not wheel.pep658_metadata_available()


@pytest.mark.asyncio
async def test_download_pep658_metadata(dummy_wheel_url):
    parsed = parse_wheel_filename(PYTEST_WHEEL)
    name = str(parsed[0])
    version = str(parsed[1])
    filename = PYTEST_WHEEL
    sha256 = "dummy-sha256"
    size = 1234

    wheel = WheelInfo.from_package_index(name, filename, dummy_wheel_url, version, sha256, size, data_dist_info_metadata=True)
    assert wheel.pep658_metadata_available()

    assert wheel._metadata is None
    await wheel.download_pep658_metadata()
    assert wheel._metadata is not None


    wheel = WheelInfo.from_package_index(name, filename, dummy_wheel_url, version, sha256, size, data_dist_info_metadata={"sha256": "dummy-sha256"})
    assert wheel.pep658_metadata_available()

    assert wheel._metadata is None
    with pytest.raises(RuntimeError, match="Invalid checksum: expected dummy-sha256"):
        await wheel.download_pep658_metadata()

    
    checksum = "62eb95408ccec185e7a3b8f354a1df1721cd8f463922f5a900c7bf4b69c5a4e8"  # TODO: calculate this from the file
    wheel = WheelInfo.from_package_index(name, filename, dummy_wheel_url, version, sha256, size, data_dist_info_metadata={"sha256": checksum})
    assert wheel.pep658_metadata_available()

    assert wheel._metadata is None
    await wheel.download_pep658_metadata()
    assert wheel._metadata is not None
