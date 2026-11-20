import pytest
from conftest import SNOWBALL_WHEEL
from pytest_pyodide import run_in_pyodide

from micropip._vendored.packaging.src.packaging.tags import Tag


@pytest.mark.parametrize(
    "path",
    [
        SNOWBALL_WHEEL,
        f"/{SNOWBALL_WHEEL}",
        f"a/{SNOWBALL_WHEEL}",
        f"/a/{SNOWBALL_WHEEL}",
        f"//a/{SNOWBALL_WHEEL}",
    ],
)
@pytest.mark.parametrize(
    "protocol",
    ["http:", "https:", "file:", "emfs:", ""],
)
def test_parse_wheel_url1(protocol, path):
    from micropip.resolver import WheelInfo

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
    from micropip.resolver import WheelInfo

    msg = r"Invalid wheel filename \(wrong number of parts\)"
    with pytest.raises(ValueError, match=msg):
        url = "https://a/snowballstemmer-2.0.0-py2.whl"
        WheelInfo.from_url(url)


def test_parse_wheel_url3():
    from micropip.resolver import WheelInfo

    url = "http://a/scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
    wheel = WheelInfo.from_url(url)
    assert wheel.name == "scikit-learn"
    assert wheel.tags == frozenset({Tag("cp35", "cp35m", "macosx_10_9_intel")})


@pytest.mark.asyncio
async def test_add_requirement(wheel_catalog, host_compat_layer):
    from micropip.resolver import Resolver

    snowballstemmer_wheel = wheel_catalog.get("snowballstemmer")

    resolver = Resolver(host_compat_layer, keep_going=True)
    await resolver.add_requirement(snowballstemmer_wheel.url)

    wheel = resolver.wheels[0]
    assert wheel.name == "snowballstemmer"
    assert str(wheel.version) == "2.0.0"
    assert wheel.filename == SNOWBALL_WHEEL
    assert wheel.url == snowballstemmer_wheel.url
    assert wheel.tags == frozenset(
        {Tag("py2", "none", "any"), Tag("py3", "none", "any")}
    )


def test_add_requirement_marker(selenium_standalone_micropip, fake_index):
    # Only "dummy" exists on the index; installing any of the other
    # requirements would fail, so this also checks they are skipped.
    fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install(
            [
                "dummy",
                'contextvars ; python_version < "3.7"',
                'aiocontextvars ; python_version < "3.7"',
                "numpy ; extra == 'full'",
                "zarr ; extra == 'full'",
                "numpy ; extra == 'jupyter'",
                "ipykernel ; extra == 'jupyter'",
                "numpy ; extra == 'socketio'",
                "python-socketio[client] ; extra == 'socketio'",
            ],
            index_urls=[index_url],
        )

        pkgs = micropip.list()
        assert "dummy" in pkgs
        for name in (
            "contextvars",
            "aiocontextvars",
            "numpy",
            "zarr",
            "ipykernel",
            "python-socketio",
        ):
            assert name not in pkgs

    run(selenium_standalone_micropip, fake_index.url)


def test_add_requirement_query_url(selenium_standalone_micropip, fake_index):
    wheel = fake_index.add_pkg_version("dummy")

    @run_in_pyodide
    async def run(selenium, url):
        import micropip

        await micropip.install(url)
        assert "dummy" in micropip.list()

    run(selenium_standalone_micropip, f"{wheel.url}?b=1")


@pytest.mark.asyncio
async def test_install_non_pure_python_wheel(host_compat_layer):
    from micropip.constants import FAQ_URLS
    from micropip.resolver import Resolver

    msg = "Wheel platform 'macosx_10_9_intel' is not compatible with Pyodide's platform"
    with pytest.raises(ValueError, match=msg) as exc_info:
        url = "http://a/scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        resolver = Resolver(host_compat_layer, keep_going=True)
        await resolver.add_requirement(url)
    assert FAQ_URLS["building_packages"] in str(exc_info.value)


@pytest.mark.parametrize(
    "url",
    [
        "git+https://github.com/example/example.git",
        "git+https://github.com/example/example.git@v1.0.0",
        "hg+https://example.com/repo",
        "svn+https://example.com/repo",
        "bzr+https://example.com/repo",
    ],
)
@pytest.mark.asyncio
async def test_add_requirement_vcs_url_helpful_error(url, host_compat_layer):
    from micropip.resolver import Resolver

    resolver = Resolver(host_compat_layer, keep_going=True)
    with pytest.raises(ValueError) as exc_info:
        await resolver.add_requirement(url)
    assert (
        "Provide a URL pointing to a wheel or a package name available on a configured index."
        in str(exc_info.value)
    )


@pytest.mark.asyncio
async def test_fetch_bytes_unexpected_url_scheme(host_compat_layer):
    from micropip.resolver import Resolver
    from micropip.wheelinfo import WheelInfo

    url = f"ftp://example.com/{SNOWBALL_WHEEL}"
    wheel = WheelInfo.from_url(url)
    resolver = Resolver(host_compat_layer)
    with pytest.raises(TypeError, match="Unexpected URL scheme 'ftp'"):
        await resolver.fetch_bytes(url, wheel)


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
    from micropip._vendored.packaging.src.packaging.requirements import Requirement
    from micropip.resolver import find_wheel

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
    from micropip._vendored.packaging.src.packaging.requirements import Requirement
    from micropip.resolver import find_wheel

    requirement = Requirement("dummy_module")
    versions = ["0.0.1", "0.15.5", "0.9.1", "2004d"]

    metadata = _pypi_metadata("dummy_module", {v: ["py3"] for v in versions})

    # get version number from find_wheel
    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == "0.15.5"


def test_yanked_version():
    from micropip._vendored.packaging.src.packaging.requirements import Requirement
    from micropip.resolver import find_wheel

    versions = ["0.0.1", "0.15.5", "0.9.1"]

    # Mark 0.15.5 as yanked
    # convert generator --> list and monkeypatch the yanked value
    metadata = _pypi_metadata("dummy_module", {v: ["py3"] for v in versions})
    for version in list(metadata.releases):
        wheels = list(metadata.releases[version])
        for wheel in wheels:
            if str(wheel.version) == "0.15.5":
                wheel.yanked = True

        metadata.releases[version] = wheels

    # case 1: yanked version should be skipped and the next best version should be selected

    requirement1 = Requirement("dummy_module")
    wheel = find_wheel(metadata, requirement1)

    assert str(wheel.version) == "0.9.1"

    # case 2: yanked version is explicitly requested, so it should be selected

    requirement2 = Requirement("dummy_module==0.15.5")
    wheel = find_wheel(metadata, requirement2)

    assert str(wheel.version) == "0.15.5"

    # case 3: yanked version is not explicitly requested, but it is the only version available
    # so it should be selected

    requirement3 = Requirement("dummy_module>0.10.0")

    wheel = find_wheel(metadata, requirement3)

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
    from micropip._vendored.packaging.src.packaging.requirements import Requirement
    from micropip.resolver import find_wheel

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
    from micropip._vendored.packaging.src.packaging.requirements import Requirement
    from micropip.resolver import find_wheel

    requirement = Requirement(package)

    metadata = _pypi_metadata(
        package,
        {old_version: old_tags, new_version: new_tags},
    )

    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == new_version


def test_search_pyodide_lock_first(host_compat_layer):
    from micropip import package_index
    from micropip.resolver import Resolver

    t = Resolver(
        compat_layer=host_compat_layer,
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

    t = Resolver(
        compat_layer=host_compat_layer,
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


def test_index_url_priority(selenium_standalone_micropip, fake_index):
    # If index_urls are provided, packages should be searched in the
    # index_urls first, before searching in the Pyodide lock file.
    # "regex" is in the Pyodide lock file, but the index has a newer version.
    fake_index.add_pkg_version("regex", "9999.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("regex", index_urls=[index_url])

        pkg = micropip.list()["regex"]
        assert pkg.version == "9999.0.0"
        assert pkg.source.lower() == "pypi"

    run(selenium_standalone_micropip, fake_index.url)


@pytest.mark.parametrize(
    "requirements",
    [
        # The same requirement twice
        ["micropip-test-dep", "micropip-test-dep"],
        # Two packages that depend on the same package
        ["micropip-test-a", "micropip-test-b"],
    ],
)
def test_shared_requirement_added_once(
    selenium_standalone_micropip, fake_index, requirements
):
    # Requirements are resolved concurrently, so a package can be found by one
    # branch while another branch is still querying the index for it. This
    # runs in Pyodide because fetching is only truly asynchronous there.
    fake_index.add_pkg_version("micropip-test-a", requirements=["micropip-test-dep"])
    fake_index.add_pkg_version("micropip-test-b", requirements=["micropip-test-dep"])
    fake_index.add_pkg_version("micropip-test-dep")

    @run_in_pyodide
    async def run(selenium, index_url, requirements):
        from micropip._compat import get_default_compatibility_layer
        from micropip.resolver import Resolver

        resolver = Resolver(
            compat_layer=get_default_compatibility_layer(), index_urls=[index_url]
        )
        await resolver.gather_requirements(requirements)

        names = [wheel.name for wheel in resolver.wheels]
        assert names.count("micropip-test-dep") == 1, names

    run(selenium_standalone_micropip, fake_index.url, requirements)


# Tests for the "PYODIDE" special value in index_urls
# https://github.com/pyodide/micropip/issues/147


@pytest.mark.parametrize(
    "index_urls,search_lock_first,expected",
    [
        # without "PYODIDE": lock file first with the default index,
        # and as a fallback after custom indexes
        (["https://pypi.org/simple"], True, [None, ["https://pypi.org/simple"]]),
        (["A", "B"], False, [["A", "B"], None]),
        ("A", False, [["A"], None]),
        ([], False, [[], None]),
        # with "PYODIDE": the lock file is searched at that position
        (["PYODIDE"], False, [None]),
        ("PYODIDE", False, [None]),
        (["PYODIDE", "A", "PYPI"], False, [None, ["A", "PYPI"]]),
        (["A", "PYODIDE"], False, [["A"], None]),
        (["A", "PYODIDE", "B", "C"], False, [["A"], None, ["B", "C"]]),
    ],
)
def test_sources(host_compat_layer, index_urls, search_lock_first, expected):
    from micropip.resolver import Resolver

    resolver = Resolver(host_compat_layer, index_urls=index_urls)
    assert resolver.search_pyodide_lock_first is search_lock_first
    assert resolver._sources() == expected


def test_project_urls_skips_pyodide():
    from micropip import package_index

    urls = package_index.project_urls("pkg", ["PYODIDE", "https://a/simple", "PYPI"])
    assert urls == ["https://a/simple/pkg/", "https://pypi.org/simple/pkg/"]
    assert package_index.project_urls("pkg", "PYODIDE") == []


def _resolver_with_lockfile(compat_layer, index_urls, **kwargs):
    from micropip.resolver import Resolver

    compat_layer.lockfile_packages = {
        "pkg": {"name": "pkg", "version": "1.0.0", "depends": []},
        "lockonly": {"name": "lockonly", "version": "1.0.0", "depends": []},
    }
    return Resolver(compat_layer, index_urls=index_urls, **kwargs)


def _sources_of(resolver):
    """Map each resolved package to "pyodide" (lock file) or its wheel version."""
    sources = {p.name: "pyodide" for p in resolver.pyodide_packages}
    sources.update({w.name: str(w.version) for w in resolver.wheels})
    return sources


@pytest.mark.asyncio
async def test_pyodide_index_first(host_compat_layer, fake_index):
    fake_index.add_pkg_version("pkg", "2.0.0")
    fake_index.add_pkg_version("indexonly")

    resolver = _resolver_with_lockfile(host_compat_layer, ["PYODIDE", fake_index.url])
    await resolver.gather_requirements(["pkg", "indexonly", "lockonly"])

    assert _sources_of(resolver) == {
        "pkg": "pyodide",
        "lockonly": "pyodide",
        "indexonly": "1.0.0",
    }


@pytest.mark.asyncio
async def test_pyodide_index_version_not_satisfied(host_compat_layer, fake_index):
    # The lock file is skipped if its version doesn't satisfy the requirement.
    fake_index.add_pkg_version("pkg", "2.0.0")

    resolver = _resolver_with_lockfile(host_compat_layer, ["PYODIDE", fake_index.url])
    await resolver.add_requirement("pkg>=2")

    assert _sources_of(resolver) == {"pkg": "2.0.0"}


@pytest.mark.asyncio
async def test_pyodide_index_last(host_compat_layer, fake_index):
    fake_index.add_pkg_version("pkg", "2.0.0")

    resolver = _resolver_with_lockfile(host_compat_layer, [fake_index.url, "PYODIDE"])
    await resolver.gather_requirements(["pkg", "lockonly"])

    assert _sources_of(resolver) == {"pkg": "2.0.0", "lockonly": "pyodide"}


@pytest.mark.asyncio
async def test_pyodide_index_in_the_middle(host_compat_layer, httpserver):
    from fake_index import FakePackageIndex

    first = FakePackageIndex(httpserver)
    last = FakePackageIndex(httpserver)
    first.add_pkg_version("firstonly", "1.0.0")
    for name in ("pkg", "firstonly", "lastonly"):
        last.add_pkg_version(name, "3.0.0")

    resolver = _resolver_with_lockfile(
        host_compat_layer, [first.url, "PYODIDE", last.url]
    )
    await resolver.gather_requirements(["pkg", "firstonly", "lastonly"])

    assert _sources_of(resolver) == {
        "firstonly": "1.0.0",
        "pkg": "pyodide",
        "lastonly": "3.0.0",
    }


@pytest.mark.asyncio
async def test_pyodide_index_only(host_compat_layer):
    # Without any other index, packages that are not in the lock file fail.
    resolver = _resolver_with_lockfile(host_compat_layer, ["PYODIDE"])
    await resolver.add_requirement("lockonly")
    assert _sources_of(resolver) == {"lockonly": "pyodide"}

    with pytest.raises(ValueError, match="'pkg>=2' in the Pyodide lock file"):
        await resolver.add_requirement("pkg>=2")
    with pytest.raises(ValueError, match="'indexonly' in the Pyodide lock file"):
        await resolver.add_requirement("indexonly")
    assert [str(r) for r in resolver.failed] == ["pkg>=2", "indexonly"]


@pytest.mark.asyncio
async def test_pyodide_index_not_found(host_compat_layer, fake_index):
    # If no source has the package, the error from the index is raised.
    fake_index.add_pkg_version("nowheel", tag="cp313-cp313-invalid")

    resolver = _resolver_with_lockfile(host_compat_layer, ["PYODIDE", fake_index.url])
    with pytest.raises(ValueError, match="Can't fetch metadata for 'missing'"):
        await resolver.add_requirement("missing")
    with pytest.raises(ValueError, match="Can't find a pure Python 3 wheel"):
        await resolver.add_requirement("nowheel")


@pytest.mark.asyncio
async def test_pyodide_index_keep_going(host_compat_layer, fake_index):
    fake_index.add_pkg_version("indexonly")

    resolver = _resolver_with_lockfile(
        host_compat_layer, ["PYODIDE", fake_index.url], keep_going=True
    )
    await resolver.gather_requirements(["missing", "pkg", "indexonly", "other"])

    assert sorted(str(r) for r in resolver.failed) == ["missing", "other"]
    assert _sources_of(resolver) == {"pkg": "pyodide", "indexonly": "1.0.0"}


def _lockfile_version(request, name):
    import json

    lockfile = request.config.option.dist_dir / "pyodide-lock.json"
    return json.loads(lockfile.read_text())["packages"][name]["version"]


def test_pyodide_index_selenium(selenium_standalone_micropip, fake_index, request):
    # "tomli" is in the Pyodide lock file (and not preloaded by pytest-pyodide).
    version = _lockfile_version(request, "tomli")
    fake_index.add_pkg_version("tomli", "9999.0.0")
    fake_index.add_pkg_version("fakepkg", top_level=["fakepkg"])

    @run_in_pyodide
    async def run(selenium, index_url, version):
        import micropip

        micropip.set_index_urls(["PYODIDE", index_url])
        await micropip.install(["tomli", "fakepkg"])

        pkg_list = micropip.list()
        assert pkg_list["tomli"].source.lower() == "pyodide"
        assert pkg_list["tomli"].version == version
        assert pkg_list["fakepkg"].source.lower() != "pyodide"
        assert pkg_list["fakepkg"].version == "1.0.0"

    run(selenium_standalone_micropip, fake_index.url, version)


def test_pyodide_index_last_selenium(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version("tomli", "9999.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("tomli", index_urls=[index_url, "PYODIDE"])

        pkg = micropip.list()["tomli"]
        assert pkg.source.lower() != "pyodide"
        assert pkg.version == "9999.0.0"

    run(selenium_standalone_micropip, fake_index.url)
