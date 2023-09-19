from pathlib import Path

import pytest
from conftest import SNOWBALL_WHEEL
from packaging.tags import Tag
from pytest_pyodide import spawn_web_server


@pytest.mark.parametrize(
    "path",
    [
        SNOWBALL_WHEEL,
        f"/{SNOWBALL_WHEEL}" f"a/{SNOWBALL_WHEEL}",
        f"/a/{SNOWBALL_WHEEL}",
        f"//a/{SNOWBALL_WHEEL}",
    ],
)
@pytest.mark.parametrize("protocol", ["https:", "file:", "emfs:", ""])
def test_parse_wheel_url1(protocol, path):
    pytest.importorskip("packaging")
    from micropip.transaction import WheelInfo

    url = protocol + path
    wheel = WheelInfo.from_url(url)
    assert wheel.name == "snowballstemmer"
    assert str(wheel.version) == "2.0.0"
    assert wheel.sha256 is None
    assert wheel.filename == SNOWBALL_WHEEL
    assert wheel.url == url
    assert wheel.tags == frozenset(
        {Tag("py2", "none", "any"), Tag("py3", "none", "any")}
    )


def test_parse_wheel_url2():
    from micropip.transaction import WheelInfo

    msg = r"Invalid wheel filename \(wrong number of parts\)"
    with pytest.raises(ValueError, match=msg):
        url = "https://a/snowballstemmer-2.0.0-py2.whl"
        WheelInfo.from_url(url)


def test_parse_wheel_url3():
    from micropip.transaction import WheelInfo

    url = "http://a/scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
    wheel = WheelInfo.from_url(url)
    assert wheel.name == "scikit-learn"
    assert wheel.tags == frozenset({Tag("cp35", "cp35m", "macosx_10_9_intel")})


def create_transaction(Transaction):
    return Transaction(
        wheels=[],
        locked={},
        keep_going=True,
        deps=True,
        pre=False,
        pyodide_packages=[],
        failed=[],
        ctx={},
        ctx_extras=[],
        fetch_kwargs={},
        index_urls=None,
    )


@pytest.mark.asyncio
async def test_add_requirement():
    pytest.importorskip("packaging")
    from micropip.transaction import Transaction

    with spawn_web_server(Path(__file__).parent / "dist") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + SNOWBALL_WHEEL

        transaction = create_transaction(Transaction)
        await transaction.add_requirement(url)

    wheel = transaction.wheels[0]
    assert wheel.name == "snowballstemmer"
    assert str(wheel.version) == "2.0.0"
    assert wheel.filename == SNOWBALL_WHEEL
    assert wheel.url == url
    assert wheel.tags == frozenset(
        {Tag("py2", "none", "any"), Tag("py3", "none", "any")}
    )


@pytest.mark.asyncio
async def test_add_requirement_marker(mock_importlib, wheel_base):
    pytest.importorskip("packaging")
    from micropip.transaction import Transaction

    transaction = create_transaction(Transaction)

    await transaction.gather_requirements(
        [
            "werkzeug",
            'contextvars ; python_version < "3.7"',
            'aiocontextvars ; python_version < "3.7"',
            "numpy ; extra == 'full'",
            "zarr ; extra == 'full'",
            "numpy ; extra == 'jupyter'",
            "ipykernel ; extra == 'jupyter'",
            "numpy ; extra == 'socketio'",
            "python-socketio[client] ; extra == 'socketio'",
        ],
    )

    non_targets = [
        "contextvars",
        "aiocontextvars",
        "numpy",
        "zarr",
        "ipykernel",
        "python-socketio",
    ]

    wheel_files = [wheel.name for wheel in transaction.wheels]
    assert "werkzeug" in wheel_files
    for t in non_targets:
        assert t not in wheel_files


@pytest.mark.asyncio
async def test_add_requirement_query_url(mock_importlib, wheel_base, monkeypatch):
    pytest.importorskip("packaging")
    from micropip.transaction import Transaction

    async def mock_add_wheel(self, wheel, extras, *, specifier=""):
        self.mock_wheel = wheel

    monkeypatch.setattr(Transaction, "add_wheel", mock_add_wheel)

    transaction = create_transaction(Transaction)
    await transaction.add_requirement(f"{SNOWBALL_WHEEL}?b=1")
    wheel = transaction.mock_wheel
    assert wheel.name == "snowballstemmer"
    assert wheel.filename == SNOWBALL_WHEEL  # without the query params


@pytest.mark.asyncio
async def test_install_non_pure_python_wheel():
    pytest.importorskip("packaging")
    from micropip.transaction import Transaction

    msg = "Wheel platform 'macosx_10_9_intel' is not compatible with Pyodide's platform"
    with pytest.raises(ValueError, match=msg):
        url = "http://a/scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        transaction = create_transaction(Transaction)
        await transaction.add_requirement(url)


def _pypi_metadata(package, versions_to_tags):
    # Build package release metadata as would be returned from
    # https://pypi.org/pypi/{pkgname}/json
    #
    # `package` is a string containing the package name as
    # it would appear in a wheel file name.
    #
    # `versions` is a mapping with version strings as
    # keys and iterables of tag strings as values.
    from micropip.package_index import ProjectInfo

    releases = {}
    for version, tags in versions_to_tags.items():
        release = []
        for tag in tags:
            wheel_name = f"{package}-{version}-{tag}-none-any.whl"
            wheel_info = {
                "filename": wheel_name,
                "url": wheel_name,
                "digests": {
                    "sha256": "0" * 64,
                },
            }
            release.append(wheel_info)
        releases[version] = release

    metadata = {"releases": releases}
    return ProjectInfo.from_json_api(metadata)


def test_last_version_from_pypi():
    pytest.importorskip("packaging")
    from packaging.requirements import Requirement

    from micropip.transaction import find_wheel

    requirement = Requirement("dummy_module")
    versions = ["0.0.1", "0.15.5", "0.9.1"]

    metadata = _pypi_metadata("dummy_module", {v: ["py3"] for v in versions})

    # get version number from find_wheel
    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == "0.15.5"


def test_find_wheel_invalid_version():
    """Check that if the one version on PyPi is unparsable

    it should be skipped instead of producing an error
    """
    pytest.importorskip("packaging")
    from packaging.requirements import Requirement

    from micropip.transaction import find_wheel

    requirement = Requirement("dummy_module")
    versions = ["0.0.1", "0.15.5", "0.9.1", "2004d"]

    metadata = _pypi_metadata("dummy_module", {v: ["py3"] for v in versions})

    # get version number from find_wheel
    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == "0.15.5"


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
def test_best_tag_from_pypi(package, version, incompatible_tags, compatible_tags):
    pytest.importorskip("packaging")
    from packaging.requirements import Requirement

    from micropip.transaction import find_wheel

    requirement = Requirement(package)
    tags = incompatible_tags + compatible_tags

    metadata = _pypi_metadata(package, {version: tags})

    wheel = find_wheel(metadata, requirement)

    best_tag = tags[-1].split(".")[-1] + "-none-any"
    assert best_tag in set(map(str, wheel.tags))


# A newer version with a compatible wheel has higher precedence
# than an older version with a more precisely compatible wheel.
# This test verifies that we didn't break that corner case:
@pytest.mark.parametrize(
    "package, old_version, old_tags, new_version, new_tags",
    [
        ("compose", "1.1.1", ["py2.py3"], "1.2.0", ["py2.py30", "py35", "py38"]),
        (
            "with_as_a_function",
            "1.0.1",
            ["py20", "py25", "py26.py3"],
            "1.1.0",
            ["py22", "py25", "py26.py30", "py33"],
        ),
    ],
)
def test_last_version_and_best_tag_from_pypi(
    package, old_version, new_version, old_tags, new_tags
):
    pytest.importorskip("packaging")
    from packaging.requirements import Requirement

    from micropip.transaction import find_wheel

    requirement = Requirement(package)

    metadata = _pypi_metadata(
        package,
        {old_version: old_tags, new_version: new_tags},
    )

    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == new_version


def test_search_pyodide_lock_first():
    from micropip import package_index
    from micropip.transaction import Transaction

    t = Transaction(
        ctx={},
        ctx_extras=[],
        keep_going=True,
        deps=True,
        pre=True,
        fetch_kwargs={},
        verbose=False,
        index_urls=package_index.DEFAULT_INDEX_URLS,
    )
    assert t.search_pyodide_lock_first is True

    t = Transaction(
        ctx={},
        ctx_extras=[],
        keep_going=True,
        deps=True,
        pre=True,
        fetch_kwargs={},
        verbose=False,
        index_urls=["https://my.custom.index.com"],
    )
    assert t.search_pyodide_lock_first is False


@pytest.mark.asyncio
async def test_index_url_priority(
    mock_importlib, wheel_base, monkeypatch, mock_package_index_simple_json_api
):
    # Test that if the index_urls are provided, package should be searched in
    # the index_urls first before searching in Pyodide lock file.
    from micropip.transaction import Transaction

    # add_wheel is called only when the package is found in the index_urls
    add_wheel_called = None

    async def mock_add_wheel(self, wheel, extras, *, specifier=""):
        nonlocal add_wheel_called
        add_wheel_called = wheel

    monkeypatch.setattr(Transaction, "add_wheel", mock_add_wheel)

    mock_index_url = mock_package_index_simple_json_api(pkgs=["black"])

    t = Transaction(
        keep_going=True,
        deps=False,
        pre=False,
        ctx={},
        ctx_extras=[],
        fetch_kwargs={},
        index_urls=mock_index_url,
    )

    await t.add_requirement("black")
    assert add_wheel_called is not None
    assert add_wheel_called.name == "black"
    # 23.7.0 is the latest version of black in the mock index
    assert str(add_wheel_called.version) == "23.7.0"
