import pytest

from micropip.wheelinfo import WheelInfo


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


def test_extract(wheel_catalog, tmp_path):
    pytest_wheel = wheel_catalog.get("pytest")
    dummy_wheel = WheelInfo.from_url(pytest_wheel.url)
    dummy_wheel._data = pytest_wheel.content

    dummy_wheel._extract(tmp_path)
    assert dummy_wheel._dist_info is not None
    assert dummy_wheel._dist_info.is_dir()


def test_set_installer(wheel_catalog, tmp_path):
    pytest_wheel = wheel_catalog.get("pytest")
    dummy_wheel = WheelInfo.from_url(pytest_wheel.url)
    dummy_wheel._data = pytest_wheel.content

    dummy_wheel._extract(tmp_path)

    dummy_wheel._set_installer()

    assert (dummy_wheel._dist_info / "INSTALLER").read_text() == "micropip"
    assert (dummy_wheel._dist_info / "PYODIDE_SOURCE").read_text() == dummy_wheel.url
    assert (dummy_wheel._dist_info / "PYODIDE_URL").read_text() == dummy_wheel.url
    assert (dummy_wheel._dist_info / "PYODIDE_SHA256").exists()


def test_install():
    pass


@pytest.mark.asyncio
async def test_download(wheel_catalog):
    pytest_wheel = wheel_catalog.get("pytest")
    wheel = WheelInfo.from_url(pytest_wheel.url)

    assert wheel._metadata is None

    await wheel.download({})

    assert wheel._metadata is not None


@pytest.mark.asyncio
async def test_requires(wheel_catalog, tmp_path):
    pytest_wheel = wheel_catalog.get("pytest")
    wheel = WheelInfo.from_url(pytest_wheel.url)
    await wheel.download({})

    wheel._extract(tmp_path)

    requirements_default = [str(r.name) for r in wheel.requires(set())]
    assert "pluggy" in requirements_default
    assert "hypothesis" not in requirements_default

    requirements_extra_testing = [str(r.name) for r in wheel.requires({"testing"})]
    assert "pluggy" in requirements_extra_testing
    assert "hypothesis" in requirements_extra_testing
