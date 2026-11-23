import pytest
from conftest import SNOWBALL_WHEEL
from pytest_pyodide import run_in_pyodide

from micropip._vendored.packaging.src.packaging.tags import Tag
from micropip.resolution import ResolveRequest


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

    resolver = Resolver(host_compat_layer, ResolveRequest(keep_going=True))
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
        resolver = Resolver(host_compat_layer, ResolveRequest(keep_going=True))
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

    resolver = Resolver(host_compat_layer, ResolveRequest(keep_going=True))
    with pytest.raises(ValueError) as exc_info:
        await resolver.add_requirement(url)
    assert (
        "Provide a URL pointing to a wheel or a package name available on a configured index."
        in str(exc_info.value)
    )


def test_fetch_unexpected_url_scheme(selenium_standalone_micropip):
    @run_in_pyodide
    async def run(selenium, url):
        import pytest

        import micropip

        # TypeError, not ValueError: ValueError would be treated as
        # "package not found" and swallowed
        with pytest.raises(TypeError, match="Unexpected URL scheme 'ftp'"):
            await micropip.install(url)

    run(selenium_standalone_micropip, f"ftp://example.com/{SNOWBALL_WHEEL}")


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
        from micropip.resolution import ResolveRequest
        from micropip.resolver import Resolver

        resolver = Resolver(
            get_default_compatibility_layer(), ResolveRequest(index_urls=[index_url])
        )
        await resolver.gather_requirements(requirements)

        names = [wheel.name for wheel in resolver.wheels]
        assert names.count("micropip-test-dep") == 1, names

    run(selenium_standalone_micropip, fake_index.url, requirements)


# Tests for the "PYODIDE" special value in index_urls
# https://github.com/pyodide/micropip/issues/147


def _expected_sources(expected):
    """Write expected ordered_sources() results with None for the lock file and URLs for indexes."""
    from micropip.sources import IndexSource, LockFileSource

    return [
        LockFileSource() if item is None else [IndexSource(url) for url in item]
        for item in expected
    ]


@pytest.mark.parametrize(
    "index_urls,expected",
    [
        # without "PYODIDE": lock file first with the default index,
        # and as a fallback after custom indexes
        (["https://pypi.org/simple"], [None, ["https://pypi.org/simple"]]),
        (["A", "B"], [["A", "B"], None]),
        ("A", [["A"], None]),
        ([], [[], None]),
        # with "PYODIDE": the lock file is searched at that position
        (["PYODIDE"], [None]),
        ("PYODIDE", [None]),
        (["PYODIDE", "A", "PYPI"], [None, ["A", "https://pypi.org/simple"]]),
        (["A", "PYODIDE"], [["A"], None]),
        (["A", "PYODIDE", "B", "C"], [["A"], None, ["B", "C"]]),
    ],
)
def test_ordered_sources(index_urls, expected):
    from micropip.sources import ordered_sources

    assert ordered_sources(index_urls) == _expected_sources(expected)


def test_project_urls_skips_pyodide():
    from micropip import package_index

    urls = package_index.project_urls("pkg", ["PYODIDE", "https://a/simple", "PYPI"])
    assert urls == ["https://a/simple/pkg/", "https://pypi.org/simple/pkg/"]
    assert package_index.project_urls("pkg", "PYODIDE") == []


def _resolver_with_lockfile(compat_layer, index_urls, **kwargs):
    from host_compat import DictLockFile

    from micropip.compat import LockedPackage
    from micropip.resolver import Resolver

    compat_layer.lockfile = DictLockFile(
        {
            "pkg": LockedPackage(name="pkg", version="1.0.0"),
            "lockonly": LockedPackage(name="lockonly", version="1.0.0"),
        }
    )
    return Resolver(compat_layer, ResolveRequest(index_urls=index_urls, **kwargs))


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


@pytest.mark.asyncio
async def test_lockfile_package_requires_pep508(host_compat_layer, fake_index):
    # LockedPackage.requires are full PEP 508 requirements: specifiers and
    # markers are honored. (The resolver follows them when constraints are set.)
    from host_compat import DictLockFile

    from micropip.compat import LockedPackage
    from micropip.resolver import Resolver

    fake_index.add_pkg_version("dep", "1.0.0")
    fake_index.add_pkg_version("dep", "2.0.0")
    host_compat_layer.lockfile = DictLockFile(
        {
            "locked": LockedPackage(
                name="locked",
                version="1.0.0",
                requires=["dep<2", "never-needed; python_version < '3'"],
            )
        }
    )
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(
            index_urls=["PYODIDE", fake_index.url],
            constraints=["unrelated==1.0"],
        ),
    )
    await resolver.gather_requirements(["locked"])

    assert [p.name for p in resolver.pyodide_packages] == ["locked"]
    assert [(w.name, str(w.version)) for w in resolver.wheels] == [("dep", "1.0.0")]


def _lockfile_resolver(compat_layer, locked, index_urls, **kwargs):
    from host_compat import DictLockFile

    from micropip.resolver import Resolver

    compat_layer.lockfile = DictLockFile({p.name: p for p in locked})
    return Resolver(compat_layer, ResolveRequest(index_urls=index_urls, **kwargs))


@pytest.mark.asyncio
async def test_lockfile_package_added_once(host_compat_layer, fake_index):
    # Two packages that depend on the same lock file package
    from micropip.compat import LockedPackage

    fake_index.add_pkg_version("app-a", requirements=["shared"])
    fake_index.add_pkg_version("app-b", requirements=["shared"])
    resolver = _lockfile_resolver(
        host_compat_layer,
        [LockedPackage(name="shared", version="1.0.0")],
        ["PYODIDE", fake_index.url],
    )
    await resolver.gather_requirements(["app-a", "app-b"])

    assert [p.name for p in resolver.pyodide_packages] == ["shared"]


class _Warnings:
    """Collect the warnings logged by micropip's logger."""

    def __init__(self):
        import logging

        self.messages: list[str] = []
        self.handler = logging.Handler(level=logging.WARNING)
        self.handler.emit = lambda record: self.messages.append(record.getMessage())

    def __enter__(self):
        import logging

        logging.getLogger("micropip").addHandler(self.handler)
        return self.messages

    def __exit__(self, *exc):
        import logging

        logging.getLogger("micropip").removeHandler(self.handler)


@pytest.mark.asyncio
async def test_conflict_with_lockfile_version(host_compat_layer, fake_index):
    # "shared" is selected from the lock file (2.0.0), then "app" needs shared<2.
    # The resolver can't backtrack: it keeps 2.0.0 with a warning, and never
    # selects a second version.
    from micropip.compat import LockedPackage

    fake_index.add_pkg_version("app", requirements=["shared<2"])
    fake_index.add_pkg_version("shared", "1.0.0")
    resolver = _lockfile_resolver(
        host_compat_layer,
        [LockedPackage(name="shared", version="2.0.0")],
        ["PYODIDE", fake_index.url],
    )
    with _Warnings() as warnings:
        await resolver.gather_requirements(["shared", "app"])

    selected = [(p.name, p.version) for p in resolver.pyodide_packages] + [
        (w.name, str(w.version)) for w in resolver.wheels
    ]
    assert sorted(selected) == [("app", "1.0.0"), ("shared", "2.0.0")]
    assert resolver.failed == []
    assert len(warnings) == 1
    assert "'shared<2' is not satisfied by shared==2.0.0" in warnings[0]
    assert "keeping shared==2.0.0" in warnings[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("reinstall", [False, True])
async def test_conflict_between_wheels(host_compat_layer, fake_index, reinstall):
    # a needs c<2, b needs c>=2: c 1.0.0 (selected first) is kept with a
    # warning. With reinstall=True, the old check let a second version through;
    # with reinstall=False, it raised a misleading "already installed" error.
    from micropip.resolver import Resolver

    fake_index.add_pkg_version("a", requirements=["c<2"])
    fake_index.add_pkg_version("b", requirements=["c>=2"])
    fake_index.add_pkg_version("c", "1.0.0")
    fake_index.add_pkg_version("c", "2.0.0")
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(
            requirements=["a", "b"], index_urls=[fake_index.url], reinstall=reinstall
        ),
    )
    with _Warnings() as warnings:
        resolution = await resolver.resolve()

    assert sorted((w.name, str(w.version)) for w in resolution.wheels) == [
        ("a", "1.0.0"),
        ("b", "1.0.0"),
        ("c", "1.0.0"),
    ]
    assert len(warnings) == 1
    assert "'c>=2' (needed by 'b') is not satisfied by c==1.0.0" in warnings[0]


@pytest.mark.asyncio
async def test_request_installed_snapshot(host_compat_layer, fake_index):
    # The resolver uses ResolveRequest.installed instead of reading the
    # environment, when it's given.
    from micropip.resolver import Resolver

    fake_index.add_pkg_version("app", requirements=["dep"])
    fake_index.add_pkg_version("dep", "2.0.0")

    # "dep" is installed (according to the snapshot): not added again
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(
            requirements=["app"],
            index_urls=[fake_index.url],
            installed={"dep": "1.0.0"},
        ),
    )
    resolution = await resolver.resolve()
    assert [w.name for w in resolution.wheels] == ["app"]

    # An installed version that doesn't satisfy the requirement
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(
            requirements=["dep>=2"],
            index_urls=[fake_index.url],
            installed={"dep": "1.0.0"},
        ),
    )
    with pytest.raises(ValueError, match=r"dep==1\.0\.0 is already installed"):
        await resolver.resolve()

    # ... is replaced with reinstall=True
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(
            requirements=["dep>=2"],
            index_urls=[fake_index.url],
            installed={"dep": "1.0.0"},
            reinstall=True,
        ),
    )
    resolution = await resolver.resolve()
    assert [(w.name, str(w.version)) for w in resolution.wheels] == [("dep", "2.0.0")]


def test_lockfile_package_extras(selenium_standalone_micropip, fake_index, request):
    # The Pyodide lock file does not record optional dependencies, so the
    # dependencies of `pkg[extra]` for a package that is installed from the
    # lock file are read from the metadata of the same version in the index.
    # https://github.com/pyodide/micropip/issues/69
    version = _lockfile_version(request, "tomli")
    fake_index.add_pkg_version("tomli", version, extras={"test": ["fakedep"]})
    fake_index.add_pkg_version("fakedep", top_level=["fakedep"])

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        # Search the lock file first, as with the default index (PyPI).
        await micropip.install("tomli[test]", index_urls=["PYODIDE", index_url])

        pkg_list = micropip.list()
        assert pkg_list["tomli"].source.lower() == "pyodide"
        assert "fakedep" in pkg_list
        assert pkg_list["fakedep"].source.lower() != "pyodide"

    run(selenium_standalone_micropip, fake_index.url)


def test_lockfile_package_extras_version_not_in_index(
    selenium_standalone_micropip, fake_index, request
):
    # If the index doesn't have the version from the lock file, the extras are
    # ignored with a warning, but the package is still installed.
    version = _lockfile_version(request, "tomli")
    fake_index.add_pkg_version("tomli", "9999.0.0", extras={"test": ["fakedep"]})
    fake_index.add_pkg_version("fakedep")

    @run_in_pyodide
    async def run(selenium, index_url, version):
        import io
        import logging

        import micropip

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger("micropip").addHandler(handler)
        try:
            await micropip.install("tomli[test]", index_urls=["PYODIDE", index_url])
        finally:
            logging.getLogger("micropip").removeHandler(handler)

        pkg_list = micropip.list()
        assert pkg_list["tomli"].source.lower() == "pyodide"
        assert pkg_list["tomli"].version == version
        assert "fakedep" not in pkg_list

        logs = stream.getvalue()
        assert f"tomli=={version} is installed from the Pyodide lock file" in logs
        assert "Ignoring extras: test" in logs

    run(selenium_standalone_micropip, fake_index.url, version)


def _lockfile_first_resolver(compat_layer, index_url, **kwargs):
    from host_compat import DictLockFile

    from micropip.compat import LockedPackage
    from micropip.resolver import Resolver

    compat_layer.lockfile = DictLockFile(
        {"pkg": LockedPackage(name="pkg", version="1.0.0", requires=["basedep"])}
    )
    # Search the lock file first, as with the default index (PyPI).
    return Resolver(
        compat_layer, ResolveRequest(index_urls=["PYODIDE", index_url], **kwargs)
    )


@pytest.mark.asyncio
async def test_lockfile_package_extras_host(host_compat_layer, fake_index):
    fake_index.add_pkg_version(
        "pkg",
        "1.0.0",
        requirements=["basedep"],
        extras={"opt": ["optdep", "basedep"], "other": ["otherdep"]},
    )
    fake_index.add_pkg_version("pkg", "2.0.0", extras={"opt": ["newdep"]})
    for dep in ("basedep", "optdep", "otherdep", "newdep"):
        fake_index.add_pkg_version(dep)

    resolver = _lockfile_first_resolver(host_compat_layer, fake_index.url)
    await resolver.add_requirement("pkg[opt]")

    assert [(p.name, p.source) for p in resolver.pyodide_packages] == [
        ("pkg", "pyodide")
    ]
    # Only the extra dependencies of the locked version are added. The base
    # dependencies are loaded together with the package from the lock file,
    # and the wheel of the package itself is not downloaded.
    assert [w.name for w in resolver.wheels] == ["optdep"]
    assert not resolver.failed


@pytest.mark.asyncio
async def test_lockfile_package_extras_no_deps(host_compat_layer, fake_index):
    fake_index.add_pkg_version("pkg", "1.0.0", extras={"opt": ["optdep"]})
    fake_index.add_pkg_version("optdep")

    resolver = _lockfile_first_resolver(host_compat_layer, fake_index.url, deps=False)
    await resolver.add_requirement("pkg[opt]")

    assert [p.name for p in resolver.pyodide_packages] == ["pkg"]
    assert resolver.wheels == []


@pytest.mark.parametrize(
    "version,tag,extra,reason",
    [
        # the locked version is not in the index
        ("2.0.0", "py3-none-any", "opt", "Can't find a pure Python 3 wheel"),
        # no compatible wheel (e.g. a package with compiled code)
        ("1.0.0", "cp313-cp313-invalid", "opt", "Can't find a pure Python 3 wheel"),
        ("1.0.0", "py3-none-any", "unknown", "does not provide the extra 'unknown'"),
    ],
)
@pytest.mark.asyncio
async def test_lockfile_package_extras_unavailable(
    host_compat_layer, fake_index, caplog, version, tag, extra, reason
):
    fake_index.add_pkg_version("pkg", version, tag=tag, extras={"opt": ["optdep"]})
    fake_index.add_pkg_version("optdep")

    resolver = _lockfile_first_resolver(host_compat_layer, fake_index.url)
    with caplog.at_level("WARNING", logger="micropip"):
        await resolver.add_requirement(f"pkg[{extra}]")

    # The package is still installed from the lock file, without the extras.
    assert [p.name for p in resolver.pyodide_packages] == ["pkg"]
    assert resolver.wheels == []
    assert not resolver.failed
    assert reason in caplog.text


@pytest.mark.asyncio
async def test_lockfile_package_extras_no_index(host_compat_layer, fake_index, caplog):
    resolver = _lockfile_first_resolver(host_compat_layer, fake_index.url)
    with caplog.at_level("WARNING", logger="micropip"):
        await resolver.add_requirement("pkg[opt]")

    assert [p.name for p in resolver.pyodide_packages] == ["pkg"]
    assert "Can't fetch metadata for 'pkg'" in caplog.text
    assert "Ignoring extras: opt" in caplog.text


# Extras of requirements that are already satisfied (installed, or selected in
# the same resolution) used to be ignored.


@pytest.mark.asyncio
async def test_extras_of_package_selected_earlier(host_compat_layer, fake_index):
    # "app" is selected for the first requirement, then "app[opt]" comes along
    from micropip.resolver import Resolver

    fake_index.add_pkg_version("app", extras={"opt": ["optdep"]})
    fake_index.add_pkg_version("optdep")
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(requirements=["app", "app[opt]"], index_urls=[fake_index.url]),
    )
    resolution = await resolver.resolve()

    assert sorted(w.name for w in resolution.wheels) == ["app", "optdep"]


@pytest.mark.asyncio
async def test_extras_of_lockfile_package_selected_earlier(
    host_compat_layer, fake_index
):
    fake_index.add_pkg_version(
        "pkg", "1.0.0", requirements=["basedep"], extras={"opt": ["optdep"]}
    )
    fake_index.add_pkg_version("optdep")
    resolver = _lockfile_first_resolver(host_compat_layer, fake_index.url)
    await resolver.gather_requirements(["pkg", "pkg[opt]"])

    assert [p.name for p in resolver.pyodide_packages] == ["pkg"]
    assert [w.name for w in resolver.wheels] == ["optdep"]


@pytest.mark.asyncio
async def test_unknown_extra_of_wheel_warns(host_compat_layer, fake_index):
    # Used to fail with KeyError; now warns like the lock file path (and pip)
    from micropip.resolver import Resolver

    fake_index.add_pkg_version("app", extras={"opt": ["optdep"]})
    fake_index.add_pkg_version("optdep")
    resolver = Resolver(
        host_compat_layer,
        ResolveRequest(requirements=["app[nope,opt]"], index_urls=[fake_index.url]),
    )
    with _Warnings() as warnings:
        resolution = await resolver.resolve()

    assert sorted(w.name for w in resolution.wheels) == ["app", "optdep"]
    assert warnings == ["app 1.0.0 does not provide the extra 'nope'"]


def test_extras_of_installed_package(selenium_standalone_micropip, fake_index):
    # install("app") then install("app[opt]") installs the extra's dependencies,
    # read from the installed METADATA, without reinstalling "app".
    fake_index.add_pkg_version("app", extras={"opt": ["optdep"]})
    fake_index.add_pkg_version("optdep")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("app", index_urls=[index_url])
        assert "optdep" not in micropip.list()

        resolution = await micropip.default_client.resolve(
            "app[opt]", index_urls=[index_url]
        )
        assert [w.name for w in resolution.wheels] == ["optdep"]

        await micropip.install("app[opt]", index_urls=[index_url])
        assert "optdep" in micropip.list()

    run(selenium_standalone_micropip, fake_index.url)
