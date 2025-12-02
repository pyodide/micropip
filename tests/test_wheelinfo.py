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


def test_from_url_with_percent_encoded_path():
    # Test URL with percent-encoded characters (+ encoded as %2B in version string)
    url = "https://test.com/dummy_module-1.0.0%2Blocalbuild.1-py3-none-any.whl"
    wheel = WheelInfo.from_url(url)

    assert wheel.name == "dummy-module"
    assert str(wheel.version) == "1.0.0+localbuild.1"
    assert wheel.url == url
    assert wheel.filename == "dummy_module-1.0.0+localbuild.1-py3-none-any.whl"
    assert wheel.size is None
    assert wheel.sha256 is None


def test_from_package_index():
    name = "dummy-module"
    filename = "dummy_module-0.0.1-py3-none-any.whl"
    url = "https://test.com/dummy_module-0.0.1-py3-none-any.whl"
    version = "0.0.1"
    sha256 = "dummy-sha256"
    size = 1234
    core_metadata = True

    wheel = WheelInfo.from_package_index(
        name, filename, url, version, sha256, size, core_metadata
    )

    assert wheel.name == name
    assert str(wheel.version) == version
    assert wheel.url == url
    assert wheel.filename == filename
    assert wheel.size == size
    assert wheel.sha256 == sha256
    assert wheel.core_metadata == core_metadata


@pytest.mark.asyncio
async def test_download(wheel_catalog, host_compat_layer):
    pytest_wheel = wheel_catalog.get("pytest")
    wheel = WheelInfo.from_url(pytest_wheel.url)

    assert wheel._metadata is None

    await wheel.download({}, host_compat_layer)

    assert wheel._metadata is not None


@pytest.mark.asyncio
async def test_requires(wheel_catalog, tmp_path, host_compat_layer):
    pytest_wheel = wheel_catalog.get("pytest")
    wheel = WheelInfo.from_url(pytest_wheel.url)
    await wheel.download({}, host_compat_layer)

    wheel._install(tmp_path, host_compat_layer)

    requirements_default = [str(r.name) for r in wheel.requires(set())]
    assert "pluggy" in requirements_default
    assert "hypothesis" not in requirements_default

    requirements_extra_testing = [str(r.name) for r in wheel.requires({"testing"})]
    assert "pluggy" in requirements_extra_testing
    assert "hypothesis" in requirements_extra_testing


@pytest.mark.asyncio
async def test_download_pep658_metadata(wheel_catalog, host_compat_layer):
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
        core_metadata=True,
    )

    assert wheel_with_metadata.pep658_metadata_available()
    assert wheel_with_metadata._metadata is None
    await wheel_with_metadata.download_pep658_metadata({}, host_compat_layer)
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
        core_metadata=None,
    )

    assert not wheel_without_metadata.pep658_metadata_available()
    assert wheel_without_metadata._metadata is None
    await wheel_without_metadata.download_pep658_metadata({}, host_compat_layer)
    assert wheel_without_metadata._metadata is None

    # 3) the metadata extracted from the wheel should be the same
    wheel = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        core_metadata=None,
    )

    assert wheel._metadata is None
    await wheel.download({}, host_compat_layer)
    assert wheel._metadata is not None

    assert wheel._metadata.deps == wheel_with_metadata._metadata.deps


@pytest.mark.asyncio
async def test_download_pep658_metadata_checksum(wheel_catalog, host_compat_layer):
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
        core_metadata={"sha256": "dummy-sha256"},
    )

    assert wheel._metadata is None
    with pytest.raises(RuntimeError, match="Invalid checksum: expected dummy-sha256"):
        await wheel.download_pep658_metadata({}, host_compat_layer)

    checksum = "62eb95408ccec185e7a3b8f354a1df1721cd8f463922f5a900c7bf4b69c5a4e8"  # TODO: calculate this from the file
    wheel = WheelInfo.from_package_index(
        pytest_wheel.name,
        pytest_wheel.filename,
        pytest_wheel.url,
        pytest_wheel.version,
        sha256,
        size,
        core_metadata={"sha256": checksum},
    )

    assert wheel._metadata is None
    await wheel.download_pep658_metadata({}, host_compat_layer)
    assert wheel._metadata is not None
