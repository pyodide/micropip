import pytest
from packaging.utils import parse_wheel_filename

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
    data_dist_info_metadata = True

    wheel = WheelInfo.from_package_index(name, filename, url, version, sha256, size, data_dist_info_metadata)

    assert wheel.name == name
    assert str(wheel.version) == version
    assert wheel.url == url
    assert wheel.filename == filename
    assert wheel.size == size
    assert wheel.sha256 == sha256
    assert wheel.data_dist_info_metadata == data_dist_info_metadata


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


@pytest.mark.asyncio
async def test_download_pep658_metadata(wheel_catalog):
    pytest_wheel = wheel_catalog.get("pytest")
    sha256 = "dummy-sha256"
    size = 1234

    # 1) metadata available
    wheel_with_metadata = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        data_dist_info_metadata=True,
    )

    assert wheel_with_metadata._metadata is None
    await wheel_with_metadata.download_pep658_metadata({})
    assert wheel_with_metadata._metadata is not None

    # metadata should be calculated from the metadata file
    deps = wheel_with_metadata._metadata.deps
    assert None in deps
    assert "testing" in deps

    # 2) metadata not available
    wheel_without_metadata = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        data_dist_info_metadata=None,
    )

    assert wheel_without_metadata._metadata is None
    await wheel_without_metadata.download_pep658_metadata({})
    assert wheel_without_metadata._metadata is None

    # 3) the metadata extracted from the wheel should be the same
    wheel = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        data_dist_info_metadata=None,
    )

    assert wheel._metadata is None
    await wheel.download({})
    assert wheel._metadata is not None

    assert wheel._metadata.deps == wheel_with_metadata._metadata.deps


@pytest.mark.asyncio
async def test_download_pep658_metadata_checksum(wheel_catalog):
    pytest_wheel = wheel_catalog.get("pytest")
    sha256 = "dummy-sha256"
    size = 1234

    wheel = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        data_dist_info_metadata={"sha256": "dummy-sha256"},
    )

    assert wheel._metadata is None
    with pytest.raises(RuntimeError, match="Invalid checksum: expected dummy-sha256"):
        await wheel.download_pep658_metadata({})

    checksum = "62eb95408ccec185e7a3b8f354a1df1721cd8f463922f5a900c7bf4b69c5a4e8"  # TODO: calculate this from the file
    wheel = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        data_dist_info_metadata={"sha256": checksum},
    )

    assert wheel._metadata is None
    await wheel.download_pep658_metadata({})
    assert wheel._metadata is not None