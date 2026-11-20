import json

import pytest
from pytest_pyodide import run_in_pyodide

from micropip.package_index import ProjectFile, ProjectPage
from micropip.sources import IndexSource, LockFileSource, Source, to_source

CORS = {"Access-Control-Allow-Origin": "*"}


def _json_api_release(wheel, url):
    """A JSON API (``/pypi/<name>/json``) entry for a ``fake_index`` wheel."""
    import hashlib

    return {
        "releases": {
            wheel.version: [
                {
                    "filename": wheel.filename,
                    "url": url,
                    "digests": {"sha256": hashlib.sha256(wheel.content).hexdigest()},
                }
            ]
        }
    }


def test_project_page_from_json_api_relative_urls_and_name():
    data = {
        "releases": {
            "1.0.0": [
                {
                    "filename": "pkg-1.0.0-py3-none-any.whl",
                    "url": "files/pkg-1.0.0-py3-none-any.whl",
                    "digests": {"sha256": "abc"},
                    "requires_python": ">=3.8",
                }
            ],
            "0.1.0": [],
        }
    }

    page = ProjectPage.from_json_api(
        data, base_url="https://example.com/lite/all.json", name="pkg"
    )

    # No info.name in the data: the given name is used
    assert page.name == "pkg"
    # Empty releases are skipped
    assert page.versions == ["1.0.0"]
    assert page.files == [
        ProjectFile(
            filename="pkg-1.0.0-py3-none-any.whl",
            url="https://example.com/lite/files/pkg-1.0.0-py3-none-any.whl",
            hashes={"sha256": "abc"},
            requires_python=">=3.8",
        )
    ]


def test_project_page_from_json_api_skips_invalid_release_versions():
    # A release with a non-PEP 440 version is skipped as a whole,
    # even if the version in its file names is valid.
    data = {
        "releases": {
            "not-a-version": [
                {
                    "filename": "pkg-1.0.0-py3-none-any.whl",
                    "url": "https://example.com/pkg-1.0.0-py3-none-any.whl",
                    "digests": {"sha256": "abc"},
                }
            ],
        }
    }

    page = ProjectPage.from_json_api(data, name="pkg")

    assert page.versions == []
    assert page.files == []


def test_project_page_from_response_unsupported_content_type():
    with pytest.raises(ValueError, match="unsupported content type: text/plain"):
        ProjectPage.from_response(
            "pkg", "https://example.com/pkg/", "", {"content-type": "text/plain"}
        )


def test_to_source():
    assert to_source("PYODIDE") == LockFileSource()
    assert to_source("PYPI") == IndexSource("https://pypi.org/simple")
    assert to_source("https://example.com/simple") == IndexSource(
        "https://example.com/simple"
    )
    source = IndexSource("https://example.com/simple")
    assert to_source(source) is source


@pytest.mark.parametrize(
    ("index_urls", "expected"),
    [
        ([LockFileSource(), "a"], [None, ["a"]]),
        (["a", LockFileSource(), "b"], [["a"], None, ["b"]]),
    ],
)
def test_sources_with_lockfile_source(host_compat_layer, index_urls, expected):
    from micropip.resolver import Resolver

    resolver = Resolver(host_compat_layer, index_urls=index_urls)
    assert resolver._sources() == expected


class InMemorySource(Source):
    def __init__(self, pages):
        self.pages = pages
        self.queried = []

    async def get_project(self, name, fetch):
        self.queried.append(name)
        return self.pages.get(name)


@pytest.mark.asyncio
async def test_custom_source_before_index(host_compat_layer, fake_index):
    from micropip.resolver import Resolver

    in_source = fake_index.add_pkg_version("in-source", "1.0.0")
    fake_index.add_pkg_version("in-source", "2.0.0")
    fake_index.add_pkg_version("index-only")

    # The custom source only has version 1.0.0 of "in-source". The index has a
    # newer one, but the first source that has the project wins.
    source = InMemorySource(
        {
            "in-source": ProjectPage(
                name="in-source",
                files=[ProjectFile(filename=in_source.filename, url=in_source.url)],
            )
        }
    )
    resolver = Resolver(
        host_compat_layer, index_urls=[source, fake_index.url], deps=False
    )
    await resolver.gather_requirements(["in-source", "index-only"])

    assert sorted(source.queried) == ["in-source", "index-only"]
    assert {w.name: str(w.version) for w in resolver.wheels} == {
        "in-source": "1.0.0",
        "index-only": "1.0.0",
    }


def test_all_json_source(selenium_standalone_micropip, fake_index, httpserver):
    """
    A source like JupyterLite's piplite uses: one JSON file with the JSON API
    data of many packages, looked up before the lock file, and never PyPI.
    """
    wheel = fake_index.add_pkg_version("dummy")
    # A URL relative to all.json (same host, absolute path)
    relative_url = "/" + wheel.url.split("/", 3)[3]
    httpserver.expect_request("/lite/all.json").respond_with_data(
        json.dumps({"dummy": _json_api_release(wheel, relative_url)}),
        content_type="application/json",
        headers=CORS,
    )

    @run_in_pyodide
    async def run(selenium, all_json_url, wheel_url):
        import json

        import pytest

        import micropip
        from micropip.compat import PyodideCompatibilityLayer
        from micropip.sources import ProjectPage, Source

        class AllJsonSource(Source):
            def __init__(self, url):
                self.url = url
                self.data = None

            async def get_project(self, name, fetch):
                if self.data is None:
                    self.data = json.loads((await fetch(self.url)).text())
                project = self.data.get(name)
                if project is None:
                    return None
                return ProjectPage.from_json_api(project, base_url=self.url, name=name)

        class RecordingLayer(PyodideCompatibilityLayer):
            def __init__(self):
                super().__init__()
                self.urls = []

            async def fetch(self, url, options):
                self.urls.append(url)
                return await super().fetch(url, options)

        layer = RecordingLayer()
        client = micropip.Client(compat=layer)
        client.set_index_urls([AllJsonSource(all_json_url), "PYODIDE"])

        await client.install("dummy")
        assert client.list_packages()["dummy"].version == "1.0.0"
        assert wheel_url in layer.urls

        # Not in all.json nor in the lock file, and PyPI is not consulted
        with pytest.raises(ValueError, match="not-anywhere"):
            await client.install("not-anywhere")
        assert not any("pypi" in url for url in layer.urls)

    run(
        selenium_standalone_micropip,
        httpserver.url_for("/lite/all.json"),
        wheel.url,
    )


def test_lockfile_source_object(selenium_standalone_micropip, fake_index):
    # LockFileSource() is the same as "PYODIDE"
    fake_index.add_pkg_version("regex", "9999.0.0")

    @run_in_pyodide
    async def run(selenium, index_url):
        import micropip
        from micropip.sources import LockFileSource

        await micropip.install("regex", index_urls=[LockFileSource(), index_url])
        assert micropip.list()["regex"].source == "pyodide"

    run(selenium_standalone_micropip, fake_index.url)


def test_default_client(selenium_standalone_micropip):
    @run_in_pyodide
    def run(selenium):
        import micropip

        micropip.set_index_urls(["PYODIDE", "PYPI"])
        assert micropip.default_client.index_urls == ["PYODIDE", "PYPI"]
        assert micropip.install.__self__ is micropip.default_client

    run(selenium_standalone_micropip)
