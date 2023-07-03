import asyncio
import hashlib
import importlib.metadata
import json
import logging
import warnings
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from sysconfig import get_platform
from typing import IO, Any
from urllib.parse import ParseResult, urlparse
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.tags import Tag, sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version

from ._compat import (
    REPODATA_PACKAGES,
    fetch_bytes,
    fetch_string,
    get_dynlibs,
    loadDynlib,
    loadedPackages,
    wheel_dist_info_dir,
)
from .constants import FAQ_URLS
from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel
from .package import PackageMetadata
from .package_index import ProjectInfo

logger = logging.getLogger("micropip")


@dataclass
class WheelInfo:
    name: str
    version: Version
    filename: str
    build: tuple[int, str] | tuple[()]
    tags: frozenset[Tag]
    url: str
    parsed_url: ParseResult
    project_name: str | None = None
    digests: dict[str, str] | None = None
    data: IO[bytes] | None = None
    _dist: Any = None
    dist_info: Path | None = None
    _requires: list[Requirement] | None = None

    @staticmethod
    def from_url(url: str) -> "WheelInfo":
        """Parse wheels URL and extract available metadata

        See https://www.python.org/dev/peps/pep-0427/#file-name-convention
        """
        parsed_url = urlparse(url)
        file_name = Path(parsed_url.path).name
        name, version, build, tags = parse_wheel_filename(file_name)
        return WheelInfo(
            name=name,
            version=version,
            filename=file_name,
            build=build,
            tags=tags,
            url=url,
            parsed_url=parsed_url,
        )

    def best_compatible_tag_index(self) -> int | None:
        """Get the index of the first tag in ``packaging.tags.sys_tags()`` that this wheel has.

        Since ``packaging.tags.sys_tags()`` is sorted from most specific ("best") to most
        general ("worst") compatibility, this index douples as a priority rank: given two
        compatible wheels, the one whose best index is closer to zero should be installed.

        Returns
        -------
        The index, or ``None`` if this wheel has no compatible tags.
        """
        for index, tag in enumerate(sys_tags()):
            if tag in self.tags:
                return index
        return None

    def is_compatible(self):
        if self.filename.endswith("py3-none-any.whl"):
            return True
        return self.best_compatible_tag_index() is not None

    def check_compatible(self) -> None:
        if self.is_compatible():
            return
        tag: Tag = next(iter(self.tags))
        if "emscripten" not in tag.platform:
            raise ValueError(
                f"Wheel platform '{tag.platform}' is not compatible with "
                f"Pyodide's platform '{get_platform()}'"
            )

        def platform_to_version(platform: str) -> str:
            return (
                platform.replace("-", "_")
                .removeprefix("emscripten_")
                .removesuffix("_wasm32")
                .replace("_", ".")
            )

        wheel_emscripten_version = platform_to_version(tag.platform)
        pyodide_emscripten_version = platform_to_version(get_platform())
        if wheel_emscripten_version != pyodide_emscripten_version:
            raise ValueError(
                f"Wheel was built with Emscripten v{wheel_emscripten_version} but "
                f"Pyodide was built with Emscripten v{pyodide_emscripten_version}"
            )

        abi_incompatible = True
        from sys import version_info

        version = f"{version_info.major}{version_info.minor}"
        abis = ["abi3", f"cp{version}"]
        for tag in self.tags:
            if tag.abi in abis:
                abi_incompatible = False
            break
        if abi_incompatible:
            abis_string = ",".join({tag.abi for tag in self.tags})
            raise ValueError(
                f"Wheel abi '{abis_string}' is not supported. Supported abis are 'abi3' and 'cp{version}'."
            )

        raise ValueError(
            f"Wheel interpreter version '{tag.interpreter}' is not supported."
        )

    async def _fetch_bytes(self, fetch_kwargs):
        try:
            return await fetch_bytes(self.url, fetch_kwargs)
        except OSError as e:
            if self.parsed_url.hostname in [
                "files.pythonhosted.org",
                "cdn.jsdelivr.net",
            ]:
                raise e
            else:
                raise ValueError(
                    f"Can't fetch wheel from '{self.url}'. "
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS). "
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

    async def download(self, fetch_kwargs):
        data = await self._fetch_bytes(fetch_kwargs)
        self.data = data
        with ZipFile(data) as zip_file:
            self._dist = pkg_resources_distribution_for_wheel(
                zip_file, self.name, "???"
            )

        self.project_name = self._dist.project_name
        if self.project_name == "UNKNOWN":
            self.project_name = self.name

    def validate(self):
        if self.digests is None:
            # No checksums available, e.g. because installing
            # from a different location than PyPI.
            return
        sha256_expected = self.digests["sha256"]
        assert self.data
        sha256_actual = _generate_package_hash(self.data)
        if sha256_actual != sha256_expected:
            raise ValueError("Contents don't match hash")

    def extract(self, target: Path) -> None:
        assert self.data
        with ZipFile(self.data) as zf:
            zf.extractall(target)
        dist_info_name: str = wheel_dist_info_dir(ZipFile(self.data), self.name)
        self.dist_info = target / dist_info_name

    def requires(self, extras: set[str]) -> list[str]:
        if not self._dist:
            raise RuntimeError(
                "Micropip internal error: attempted to access wheel 'requires' before downloading it?"
            )
        requires = self._dist.requires(extras)
        self._requires = requires
        return requires

    def write_dist_info(self, file: str, content: str) -> None:
        assert self.dist_info
        (self.dist_info / file).write_text(content)

    def set_installer(self) -> None:
        assert self.data
        wheel_source = "pypi" if self.digests is not None else self.url

        self.write_dist_info("PYODIDE_SOURCE", wheel_source)
        self.write_dist_info("PYODIDE_URL", self.url)
        self.write_dist_info("PYODIDE_SHA256", _generate_package_hash(self.data))
        self.write_dist_info("INSTALLER", "micropip")
        if self._requires:
            self.write_dist_info(
                "PYODIDE_REQUIRES", json.dumps(sorted(x.name for x in self._requires))
            )
        name = self.project_name
        assert name
        setattr(loadedPackages, name, wheel_source)

    async def load_libraries(self, target: Path) -> None:
        assert self.data
        dynlibs = get_dynlibs(self.data, ".whl", target)
        await asyncio.gather(*map(lambda dynlib: loadDynlib(dynlib, False), dynlibs))

    async def install(self, target: Path) -> None:
        if not self.data:
            raise RuntimeError(
                "Micropip internal error: attempted to install wheel before downloading it?"
            )
        self.validate()
        self.extract(target)
        await self.load_libraries(target)
        self.set_installer()


@dataclass
class Transaction:
    ctx: dict[str, str]
    ctx_extras: list[dict[str, str]]
    keep_going: bool
    deps: bool
    pre: bool
    fetch_kwargs: dict[str, str]

    locked: dict[str, PackageMetadata] = field(default_factory=dict)
    wheels: list[WheelInfo] = field(default_factory=list)
    pyodide_packages: list[PackageMetadata] = field(default_factory=list)
    failed: list[Requirement] = field(default_factory=list)

    verbose: bool | int = False

    async def gather_requirements(
        self,
        requirements: list[str],
    ) -> None:
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(self.add_requirement(requirement))

        await asyncio.gather(*requirement_promises)

    async def add_requirement(self, req: str | Requirement) -> None:
        if isinstance(req, Requirement):
            return await self.add_requirement_inner(req)

        if not urlparse(req).path.endswith(".whl"):
            return await self.add_requirement_inner(Requirement(req))

        # custom download location
        wheel = WheelInfo.from_url(req)
        wheel.check_compatible()

        await self.add_wheel(wheel, extras=set(), specifier="")

    def check_version_satisfied(self, req: Requirement) -> tuple[bool, str]:
        ver = None
        try:
            ver = importlib.metadata.version(req.name)
        except PackageNotFoundError:
            pass
        if req.name in self.locked:
            ver = self.locked[req.name].version

        if not ver:
            return False, ""

        if req.specifier.contains(ver, prereleases=True):
            # installed version matches, nothing to do
            return True, ver

        raise ValueError(
            f"Requested '{req}', " f"but {req.name}=={ver} is already installed"
        )

    async def add_requirement_inner(
        self,
        req: Requirement,
    ) -> None:
        """Add a requirement to the transaction.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        for e in req.extras:
            self.ctx_extras.append({"extra": e})

        if self.pre:
            req.specifier.prereleases = True

        if req.marker:
            # handle environment markers
            # https://www.python.org/dev/peps/pep-0508/#environment-markers

            # For a requirement being installed as part of an optional feature
            # via the extra specifier, the evaluation of the marker requires
            # the extra key in self.ctx to have the value specified in the
            # primary requirement.

            # The req.extras attribute is only set for the primary requirement
            # and hence has to be available during the evaluation of the
            # dependencies. Thus, we use the self.ctx_extras attribute above to
            # store all the extra values we come across during the transaction and
            # attempt the marker evaluation for all of these values. If any of the
            # evaluations return true we include the dependency.

            def eval_marker(e: dict[str, str]) -> bool:
                self.ctx.update(e)
                # need the assertion here to make mypy happy:
                # https://github.com/python/mypy/issues/4805
                assert req.marker is not None
                return req.marker.evaluate(self.ctx)

            self.ctx.update({"extra": ""})
            # The current package may have been brought into the transaction
            # without any of the optional requirement specification, but has
            # another marker, such as implementation_name. In this scenario,
            # self.ctx_extras is empty and hence the eval_marker() function
            # will not be called at all.
            if not req.marker.evaluate(self.ctx) and not any(
                [eval_marker(e) for e in self.ctx_extras]
            ):
                return
        # Is some version of this package is already installed?
        req.name = canonicalize_name(req.name)

        satisfied, ver = self.check_version_satisfied(req)
        if satisfied:
            logger.info(f"Requirement already satisfied: {req} ({ver})")
            return

        # If there's a Pyodide package that matches the version constraint, use
        # the Pyodide package instead of the one on PyPI
        if req.name in REPODATA_PACKAGES and req.specifier.contains(
            REPODATA_PACKAGES[req.name]["version"], prereleases=True
        ):
            version = REPODATA_PACKAGES[req.name]["version"]
            self.pyodide_packages.append(
                PackageMetadata(name=req.name, version=str(version), source="pyodide")
            )
            return

        metadata: ProjectInfo = await _get_pypi_json(req.name, self.fetch_kwargs)

        try:
            wheel = find_wheel(metadata, req)
        except ValueError:
            self.failed.append(req)
            if not self.keep_going:
                raise
            else:
                return

        # Maybe while we were downloading pypi_json some other branch
        # installed the wheel?
        satisfied, ver = self.check_version_satisfied(req)
        if satisfied:
            logger.info(f"Requirement already satisfied: {req} ({ver})")
            return

        await self.add_wheel(wheel, req.extras, specifier=str(req.specifier))

    async def add_wheel(
        self,
        wheel: WheelInfo,
        extras: set[str],
        *,
        specifier: str = "",
    ) -> None:
        """
        Download a wheel, and add its dependencies to the transaction.

        Parameters
        ----------
        wheel
            The wheel to add.

        extras
            Markers for optional dependencies.
            For example, `micropip.install("pkg[test]")`
            will pass `{"test"}` as the extras argument.

        specifier
            Requirement specifier, used only for logging.
            For example, `micropip.install("pkg>=1.0.0,!=2.0.0")`
            will pass `>=1.0.0,!=2.0.0` as the specifier argument.
        """
        normalized_name = canonicalize_name(wheel.name)
        self.locked[normalized_name] = PackageMetadata(
            name=wheel.name,
            version=str(wheel.version),
        )

        logger.info(f"Collecting {wheel.name}{specifier}")
        logger.info(f"  Downloading {wheel.url.split('/')[-1]}")

        await wheel.download(self.fetch_kwargs)
        if self.deps:
            await self.gather_requirements(wheel.requires(extras))

        self.wheels.append(wheel)


def find_wheel(metadata: ProjectInfo, req: Requirement) -> WheelInfo:
    """Parse metadata to find the latest version of pure python wheel.
    Parameters
    ----------
    metadata : ProjectInfo
    req : Requirement

    Returns
    -------
    wheel : WheelInfo
    """

    releases = metadata.releases

    candidate_versions = sorted(
        req.specifier.filter(releases),
        reverse=True,
    )

    for ver in candidate_versions:
        if ver not in releases:
            warnings.warn(
                f"The package '{metadata.name}' contains an invalid version: '{ver}'. This version will be skipped",
                stacklevel=1,
            )
            continue

        best_wheel = None
        best_tag_index = float("infinity")

        files = releases[ver]
        for fileinfo in files:
            url = fileinfo.url
            
            if not url.endswith(".whl"):
                continue

            wheel = WheelInfo.from_url(url)
            tag_index = wheel.best_compatible_tag_index()
            if tag_index is not None and tag_index < best_tag_index:
                wheel.digests = fileinfo["digests"]
                best_wheel = wheel
                best_tag_index = tag_index

        if best_wheel is not None:
            return wheel

    raise ValueError(
        f"Can't find a pure Python 3 wheel for '{req}'.\n"
        f"See: {FAQ_URLS['cant_find_wheel']}\n"
        "You can use `await micropip.install(..., keep_going=True)` "
        "to get a list of all packages with missing wheels."
    )


async def _get_pypi_json(pkgname: str, fetch_kwargs: dict[str, str]) -> ProjectInfo:
    url = f"https://pypi.org/pypi/{pkgname}/json"
    try:
        metadata = await fetch_string(url, fetch_kwargs)
    except OSError as e:
        raise ValueError(
            f"Can't fetch metadata for '{pkgname}' from PyPI. "
            "Please make sure you have entered a correct package name."
        ) from e
    return ProjectInfo.from_json_api(json.loads(metadata))


def _generate_package_hash(data: IO[bytes]) -> str:
    sha256_hash = hashlib.sha256()
    data.seek(0)
    while chunk := data.read(4096):
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
