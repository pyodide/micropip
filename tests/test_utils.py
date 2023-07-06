from contextlib import contextmanager
from importlib.metadata import distribution

import pytest
from conftest import CPVER, EMSCRIPTEN_VER, PLATFORM

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


@contextmanager
def does_not_raise():
    yield


def raiseValueError(msg):
    return pytest.raises(ValueError, match=msg)


@pytest.mark.parametrize(
    "interp, abi, arch,ctx",
    [
        (
            "cp35",
            "cp35m",
            "macosx_10_9_intel",
            raiseValueError(
                f"Wheel platform 'macosx_10_9_intel' .* Pyodide's platform '{PLATFORM}'"
            ),
        ),
        (
            "cp35",
            "cp35m",
            "emscripten_2_0_27_wasm32",
            raiseValueError(
                f"Emscripten v2.0.27 but Pyodide was built with Emscripten v{EMSCRIPTEN_VER}"
            ),
        ),
        (
            "cp35",
            "cp35m",
            PLATFORM,
            raiseValueError(
                f"Wheel abi 'cp35m' .* Supported abis are 'abi3' and '{CPVER}'."
            ),
        ),
        ("cp35", "abi3", PLATFORM, does_not_raise()),
        (CPVER, "abi3", PLATFORM, does_not_raise()),
        (CPVER, CPVER, PLATFORM, does_not_raise()),
        (
            "cp35",
            CPVER,
            PLATFORM,
            raiseValueError("Wheel interpreter version 'cp35' is not supported."),
        ),
        (
            "cp391",
            "abi3",
            PLATFORM,
            raiseValueError("Wheel interpreter version 'cp391' is not supported."),
        ),
    ],
)
def test_check_compatible(mock_platform, interp, abi, arch, ctx):
    from micropip._utils import check_compatible

    pkg = "scikit_learn-0.22.2.post1"
    wheel_name = f"{pkg}-{interp}-{abi}-{arch}.whl"
    with ctx:
        check_compatible(wheel_name)


_best_tag_test_cases = (
    "package, version, incompatible_tags, compatible_tags",
    # Tests assume that `compatible_tags` is sorted from least to most compatible:
    [
        # Common modern case (pure Python 3-only wheel):
        ("hypothesis", "6.60.0", [], ["py3"]),
        # Common historical case (pure Python 2-or-3 wheel):
        ("attrs", "22.1.0", [], ["py2.py3"]),
        # Still simple, less common (separate Python 2 and 3 wheels):
        ("raise", "1.1.9", ["py2"], ["py3"]),
        # More complicated, rarer cases:
        ("compose", "1.4.8", [], ["py2.py30", "py35", "py38"]),
        ("with_as_a_function", "1.0.1", ["py20", "py25"], ["py26.py3"]),
        ("with_as_a_function", "1.1.0", ["py22", "py25"], ["py26.py30", "py33"]),
    ],
)


@pytest.mark.parametrize(*_best_tag_test_cases)
def test_best_compatible_tag(package, version, incompatible_tags, compatible_tags):
    from micropip._utils import best_compatible_tag_index, parse_tags

    for tag in incompatible_tags:
        wheel_name = f"{package}-{version}-{tag}-none-any.whl"
        assert best_compatible_tag_index(parse_tags(wheel_name)) is None

    tags = []
    for tag in compatible_tags:
        wheel_name = f"{package}-{version}-{tag}-none-any.whl"
        tags.append(parse_tags(wheel_name))

    sorted_tags = sorted(tags, key=best_compatible_tag_index)
    sorted_tags.reverse()
    assert sorted_tags == tags
