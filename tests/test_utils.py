from importlib.metadata import distribution

import micropip._utils as _utils


def test_get_root():
    dist = distribution("pytest")
    root = _utils.get_root(dist)

    assert (root / "pytest").is_dir()


def test_get_dist_info():
    dist = distribution("pytest")
    dist_info = _utils.get_dist_info(dist)

    assert dist_info.is_dir()
    assert dist_info.name.endswith(".dist-info")
    assert dist_info / "METADATA" in dist_info.iterdir()
    assert dist_info / "RECORD" in dist_info.iterdir()


def test_get_files_in_distribution():
    dist = distribution("pytest")
    files = _utils.get_files_in_distribution(dist)

    assert files
    for file in files:
        assert file.is_file()

    dist_files = dist.files
    for file in dist_files:
        assert file.locate().resolve() in files, f"{file.locate()} not found"

    dist_info = _utils.get_dist_info(dist)
    for file in dist_info.iterdir():
        assert file in files, f"{file} not found"
