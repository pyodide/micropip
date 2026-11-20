"""
A fake package index for tests.

It builds small wheels on the fly and serves them, together with a PEP 691
(Simple JSON API) project page and PEP 658 metadata files, from a local HTTP
server. Because everything goes over real HTTP, the same index can be used from
the host and from inside Pyodide, so tests can exercise micropip end-to-end
without monkeypatching any of its internals.
"""

import base64
import hashlib
import io
import json
import re
import secrets
import zipfile
from dataclasses import dataclass, field

from pytest_httpserver import HTTPServer
from werkzeug import Request, Response


def cors_headers(request: Request) -> dict[str, str]:
    """
    CORS headers that allow the request from any origin, including requests
    with ``credentials: "include"``. Browsers reject ``Access-Control-Allow-Origin: *``
    for those, so the request's origin is echoed back instead.
    """
    origin = request.headers.get("Origin")
    if origin is None:
        return {"Access-Control-Allow-Origin": "*"}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


SIMPLE_JSON_CONTENT_TYPE = "application/vnd.pypi.simple.v1+json"


def canonicalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_wheel(
    name: str,
    version: str,
    *,
    tag: str = "py3-none-any",
    requirements: list[str] | None = None,
    extras: dict[str, list[str]] | None = None,
    top_level: list[str] | None = None,
    files: dict[str, str] | None = None,
) -> tuple[str, bytes, bytes]:
    """
    Build a minimal wheel in memory.

    Returns a tuple of (filename, wheel bytes, METADATA bytes).
    """
    requirements = requirements or []
    extras = extras or {}
    top_level = top_level or []
    files = files or {}

    dist_name = re.sub(r"[-_.]+", "_", name).lower()
    dist_info = f"{dist_name}-{version}.dist-info"
    filename = f"{dist_name}-{version}-{tag}.whl"

    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    metadata_lines += [f"Requires-Dist: {req}" for req in requirements]
    for extra, reqs in extras.items():
        metadata_lines.append(f"Provides-Extra: {extra}")
        metadata_lines += [f"Requires-Dist: {req}; extra == {extra!r}" for req in reqs]
    metadata = ("\n".join(metadata_lines) + "\n").encode()

    contents: dict[str, bytes] = {
        path: content.encode() for path, content in files.items()
    }
    contents[f"{dist_info}/METADATA"] = metadata
    contents[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: micropip-tests\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    ).encode()
    contents[f"{dist_info}/top_level.txt"] = ("\n".join(top_level) + "\n").encode()

    record_path = f"{dist_info}/RECORD"
    record_lines = [
        f"{path},{_record_hash(data)},{len(data)}" for path, data in contents.items()
    ]
    record_lines.append(f"{record_path},,")
    contents[record_path] = ("\n".join(record_lines) + "\n").encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in contents.items():
            zf.writestr(path, data)

    return filename, buf.getvalue(), metadata


@dataclass
class FakeWheel:
    name: str
    version: str
    filename: str
    url: str
    content: bytes
    metadata: bytes
    yanked: bool | str = False


@dataclass
class FakeProject:
    name: str
    wheels: dict[str, FakeWheel] = field(default_factory=dict)


class FakePackageIndex:
    """
    A package index served over HTTP that hosts wheels built on the fly.

    Usage::

        index.add_pkg_version("dummy", requirements=["dep"])
        index.add_pkg_version("dep")
        await micropip.install("dummy", index_urls=[index.url])

    Each instance is served under a random path prefix, so several instances
    can share a single HTTP server.
    """

    def __init__(self, httpserver: HTTPServer):
        self._httpserver = httpserver
        self._prefix = f"/{secrets.token_hex(8)}"
        self._projects: dict[str, FakeProject] = {}
        self._files: dict[str, bytes] = {}

        httpserver.expect_request(
            re.compile(f"^{re.escape(self._prefix)}/.*")
        ).respond_with_handler(self._handle)

    @property
    def url(self) -> str:
        """The URL to pass to ``index_urls``."""
        return self._httpserver.url_for(f"{self._prefix}/simple")

    def add_pkg_version(
        self,
        name: str,
        version: str = "1.0.0",
        *,
        tag: str = "py3-none-any",
        requirements: list[str] | None = None,
        extras: dict[str, list[str]] | None = None,
        top_level: list[str] | None = None,
        files: dict[str, str] | None = None,
        yanked: bool | str = False,
    ) -> FakeWheel:
        """
        Build a wheel and publish it on the index.

        The wheel can be installed either by name through the index, or directly
        from the returned ``FakeWheel.url``.
        """
        filename, content, metadata = build_wheel(
            name,
            version,
            tag=tag,
            requirements=requirements,
            extras=extras,
            top_level=top_level,
            files=files,
        )
        url = self._httpserver.url_for(f"{self._prefix}/files/{filename}")
        wheel = FakeWheel(
            name=name,
            version=version,
            filename=filename,
            url=url,
            content=content,
            metadata=metadata,
            yanked=yanked,
        )

        project = self._projects.setdefault(
            canonicalize_name(name), FakeProject(name=name)
        )
        project.wheels[filename] = wheel
        self._files[filename] = content
        self._files[f"{filename}.metadata"] = metadata
        return wheel

    def _project_page(self, project: FakeProject) -> bytes:
        files = [
            {
                "filename": wheel.filename,
                "url": wheel.url,
                "hashes": {"sha256": _sha256(wheel.content)},
                "core-metadata": {"sha256": _sha256(wheel.metadata)},
                "size": len(wheel.content),
                "yanked": wheel.yanked,
            }
            for wheel in project.wheels.values()
        ]
        versions = sorted({wheel.version for wheel in project.wheels.values()})
        return json.dumps(
            {
                "meta": {"api-version": "1.1"},
                "name": canonicalize_name(project.name),
                "versions": versions,
                "files": files,
            }
        ).encode()

    def _handle(self, request: Request) -> Response:
        headers = cors_headers(request)
        path = request.path.removeprefix(self._prefix)

        if path.startswith("/files/"):
            data = self._files.get(path.removeprefix("/files/"))
            if data is None:
                return Response("Not found", status=404, headers=headers)
            return Response(
                data, content_type="application/octet-stream", headers=headers
            )

        if path.startswith("/simple/"):
            name = path.removeprefix("/simple/").strip("/")
            project = self._projects.get(canonicalize_name(name))
            if project is None:
                return Response("Not found", status=404, headers=headers)
            return Response(
                self._project_page(project),
                content_type=SIMPLE_JSON_CONTENT_TYPE,
                headers=headers,
            )

        return Response("Not found", status=404, headers=headers)
