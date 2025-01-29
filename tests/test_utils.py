from contextlib import contextmanager
from importlib.metadata import distribution

import pytest
from conftest import CPVER, EMSCRIPTEN_VER, INVALID_CONSTRAINT_MESSAGES, PLATFORM
from pytest_pyodide import run_in_pyodide

import micropip._utils as _utils
from micropip._vendored.packaging.src.packaging.requirements import Requirement


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


@run_in_pyodide
def test_check_compatible_wasm32(selenium_standalone_micropip):
    """
    Here we check in particular that pyodide_2024_0_wasm32 wheels are seen as
    compatible as the platform is emscripten
    """
    from micropip._utils import check_compatible

    wheel_name = "pywavelets-1.8.0.dev0-cp312-cp312-pyodide_2024_0_wasm32.whl"
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


def test_validate_constraints_valid(valid_constraint):
    constraints = [valid_constraint] if valid_constraint else []
    reqs, msgs = _utils.validate_constraints(constraints)
    assert len(reqs) == len(constraints)
    assert not msgs

    if not valid_constraint or "==" not in valid_constraint:
        return

    extra_constraint = valid_constraint.replace("==", ">=")
    marker_valid_constraint = f"{extra_constraint} ; python_version>'2.7'"
    marker_invalid_constraint = f"{extra_constraint} ; python_version<'3'"
    constraints += [
        extra_constraint,
        marker_valid_constraint,
        marker_invalid_constraint,
    ]

    reqs, msgs = _utils.validate_constraints(constraints)
    assert "updated existing" in f"{msgs[extra_constraint]}"
    assert "updated existing" in f"{msgs[marker_valid_constraint]}"
    assert "not applicable" in f"{msgs[marker_invalid_constraint]}"


def test_validate_constraints_invalid(invalid_constraint):
    reqs, msgs = _utils.validate_constraints([invalid_constraint])
    assert not reqs
    for constraint, msg in msgs.items():
        assert INVALID_CONSTRAINT_MESSAGES[constraint] in f"{msg}"


def test_constrain_requirement(valid_constraint):
    req = Requirement("pytest")
    constraints = [valid_constraint] if valid_constraint else []
    assert not req.specifier
    constrained_reqs, msg = _utils.validate_constraints(constraints)
    assert not msg
    constrained = _utils.constrain_requirement(req, constrained_reqs)

    if constraints:
        assert constrained.specifier or constrained.url
        assert not (constrained.specifier and constrained.url)
    else:
        assert not (constrained.specifier or constrained.url)


def test_constrain_requirement_direct_url(valid_constraint, wheel_catalog):
    constraints = [valid_constraint] if valid_constraint else []
    wheel = wheel_catalog.get("pytest")
    url = f"{wheel.url}?foo"
    req = Requirement(f"pytest @ {url}")
    assert not req.specifier
    constrained_reqs, msg = _utils.validate_constraints(constraints)
    assert not msg
    constrained = _utils.constrain_requirement(req, constrained_reqs)
    assert constrained.url == url
