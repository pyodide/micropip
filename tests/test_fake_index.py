import json
import zipfile
from io import BytesIO
from urllib.request import urlopen

from fake_index import SIMPLE_JSON_CONTENT_TYPE, build_wheel
from pytest_pyodide import run_in_pyodide

from micropip.package_index import ProjectInfo


def test_build_wheel():
    filename, content, metadata = build_wheel(
        "Dummy-Pkg",
        "1.2.3",
        requirements=["dep1"],
        extras={"opt": ["dep2"]},
        top_level=["dummy_pkg"],
        files={"dummy_pkg/__init__.py": "x = 1\n"},
    )

    assert filename == "dummy_pkg-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(BytesIO(content)) as zf:
        names = set(zf.namelist())
        assert zf.read("dummy_pkg-1.2.3.dist-info/METADATA") == metadata
        assert zf.read("dummy_pkg/__init__.py") == b"x = 1\n"

    assert names == {
        "dummy_pkg/__init__.py",
        "dummy_pkg-1.2.3.dist-info/METADATA",
        "dummy_pkg-1.2.3.dist-info/WHEEL",
        "dummy_pkg-1.2.3.dist-info/top_level.txt",
        "dummy_pkg-1.2.3.dist-info/RECORD",
    }
    assert b"Requires-Dist: dep1\n" in metadata
    assert b"Provides-Extra: opt\n" in metadata
    assert b"Requires-Dist: dep2; extra == 'opt'\n" in metadata


def test_fake_index_project_page(fake_index):
    fake_index.add_pkg_version("dummy", "1.0.0")
    wheel = fake_index.add_pkg_version("dummy", "2.0.0")

    with urlopen(f"{fake_index.url}/Dummy/") as resp:
        assert resp.headers["content-type"] == SIMPLE_JSON_CONTENT_TYPE
        page = json.loads(resp.read())

    assert page["versions"] == ["1.0.0", "2.0.0"]

    project = ProjectInfo.from_simple_json_api(page)
    assert [str(v) for v in project.releases] == ["1.0.0", "2.0.0"]

    with urlopen(wheel.url) as resp:
        assert resp.read() == wheel.content
    with urlopen(wheel.url + ".metadata") as resp:
        assert resp.read() == wheel.metadata


def test_fake_index_install(selenium_standalone_micropip, fake_index):
    fake_index.add_pkg_version(
        "dummy",
        requirements=["dep"],
        top_level=["dummy"],
        files={"dummy/__init__.py": "VALUE = 42\n"},
    )
    fake_index.add_pkg_version("dep")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip

        await micropip.install("dummy", index_urls=[index_url])

        import dummy

        assert dummy.VALUE == 42

        pkgs = micropip.list()
        assert "dummy" in pkgs
        assert "dep" in pkgs

    run(selenium_standalone_micropip, fake_index.url)
