from io import BytesIO
import pytest

from micropip.wheelinfo import WheelInfo
from conftest import TEST_WHEEL_DIR, PYTEST_WHEEL


@pytest.fixture
def dummy_wheel():
    yield WheelInfo.from_url(f"https://test.com/{PYTEST_WHEEL}")


@pytest.fixture
def dummy_wheel_content():
    yield BytesIO((TEST_WHEEL_DIR / PYTEST_WHEEL).read_bytes())


@pytest.fixture
def dummy_wheel_url(httpserver):
    httpserver.expect_request(f"/{PYTEST_WHEEL}").respond_with_data(
        (TEST_WHEEL_DIR / PYTEST_WHEEL).read_bytes(),
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


def test_validate(dummy_wheel):
    import hashlib

    dummy_wheel.sha256 = None
    dummy_wheel._data = BytesIO(b"dummy-data")

    # Should succeed when sha256 is None
    dummy_wheel._validate()

    # Should fail when checksum is different
    dummy_wheel.sha256 = "dummy-sha256"
    with pytest.raises(ValueError, match="Contents don't match hash"):
        dummy_wheel._validate()
    
    # Should succeed when checksum is the same
    dummy_wheel.sha256 = hashlib.sha256(b"dummy-data").hexdigest()
    dummy_wheel._validate()


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

    assert wheel._project_name is None
    assert wheel._dist is None

    await wheel.download({})

    assert wheel._project_name == "pytest"
    assert wheel._dist is not None
    

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

