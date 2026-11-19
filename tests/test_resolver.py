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
    from micropip.resolver import Resolver

    msg = "Wheel platform 'macosx_10_9_intel' is not compatible with Pyodide's platform"
    with pytest.raises(ValueError, match=msg):
        url = "http://a/scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        resolver = Resolver(host_compat_layer, keep_going=True)
        await resolver.add_requirement(url)


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


def _lockfile_version(request, name):
    import json

    lockfile = request.config.option.dist_dir / "pyodide-lock.json"
    return json.loads(lockfile.read_text())["packages"][name]["version"]


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
        from micropip import package_index

        # Search the lock file first, as with the default index (PyPI).
        package_index.DEFAULT_INDEX_URLS[:] = [index_url]

        await micropip.install("tomli[test]", index_urls=[index_url])

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
        from micropip import package_index

        package_index.DEFAULT_INDEX_URLS[:] = [index_url]

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger("micropip").addHandler(handler)
        try:
            await micropip.install("tomli[test]", index_urls=[index_url])
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
    from micropip.resolver import Resolver

    compat_layer.lockfile_packages = {
        "pkg": {"name": "pkg", "version": "1.0.0", "depends": ["basedep"]},
    }
    resolver = Resolver(compat_layer, index_urls=[index_url], **kwargs)
    # Behave as with the default index (PyPI): search the lock file first.
    resolver.search_pyodide_lock_first = True
    return resolver


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
