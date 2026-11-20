import asyncio
import importlib.metadata
import logging
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from importlib.metadata import PackageNotFoundError
from urllib.parse import urlparse

from . import package_index
from ._compat import CompatibilityLayer, FetchOptions
from ._utils import (
    check_compatible,
    constrain_requirement,
    validate_constraints,
)
from ._vendored.packaging.src.packaging.markers import default_environment
from ._vendored.packaging.src.packaging.requirements import (
    InvalidRequirement,
    Requirement,
)
from ._vendored.packaging.src.packaging.utils import canonicalize_name
from .constants import FAQ_URLS, YANKED_WARNING_MESSAGE
from .package import PackageMetadata
from .package_index import ProjectInfo
from .wheelinfo import WheelInfo

logger = logging.getLogger("micropip")

_VCS_URL_PREFIXES = ("git+", "hg+", "svn+", "bzr+")


def _looks_like_vcs_url(req: str) -> bool:
    return req.startswith(_VCS_URL_PREFIXES)


@dataclass
class Resolver:
    """
    Resolver finds the wheels and lock file packages that satisfy a set of
    requirements, and downloads the wheels.

    All access to the network goes through ``compat_layer``. Subclasses can
    override methods such as :meth:`query_package`, :meth:`find_wheel`,
    :meth:`download_wheel` or :meth:`fetch_bytes` to customize how packages are
    found and fetched.
    """

    compat_layer: CompatibilityLayer

    ctx: dict[str, str] = field(
        default_factory=lambda: dict(default_environment())  # type: ignore[arg-type]
    )
    ctx_extras: list[dict[str, str]] = field(default_factory=list)
    keep_going: bool = False
    deps: bool = True
    pre: bool = False
    fetch_options: FetchOptions = field(default_factory=FetchOptions)
    """Fetch options for all requests (package index pages, wheels and their metadata)."""
    index_urls: list[str] | str = field(
        default_factory=lambda: package_index.DEFAULT_INDEX_URLS[:]
    )

    locked: dict[str, PackageMetadata] = field(default_factory=dict)
    wheels: list[WheelInfo] = field(default_factory=list)
    pyodide_packages: list[PackageMetadata] = field(default_factory=list)
    failed: list[Requirement] = field(default_factory=list)

    verbose: bool | int | None = None
    constraints: list[str] | None = None
    reinstall: bool = False

    def __post_init__(self) -> None:
        # With the default index (PyPI), pyodide-lock.json has to be searched first.
        # Only used if index_urls does not contain "PYODIDE", see _sources().
        # TODO: when PyPI starts to support hosting WASM wheels, this might be deleted.
        self.search_pyodide_lock_first = (
            self.index_urls == package_index.DEFAULT_INDEX_URLS
        )

        self.constrained_reqs, messages = validate_constraints(
            self.constraints, self.ctx
        )

        if self.verbose and messages:
            for constraint, msg in messages.items():
                logger.info("Resolver: constraint %s discarded: %s", constraint, msg)

    async def gather_requirements(
        self,
        requirements: list[str] | list[Requirement],
    ) -> None:
        requirement_promises = [
            self.add_requirement(requirement) for requirement in requirements
        ]

        await asyncio.gather(*requirement_promises)

    async def add_requirement(self, req: str | Requirement) -> None:
        if isinstance(req, Requirement):
            return await self.add_requirement_inner(req)

        if isinstance(req, str) and _looks_like_vcs_url(req):
            raise ValueError(
                f"Cannot install {req!r}: micropip only installs prebuilt wheels "
                "and does not support installing from a VCS URL "
                "(git+, hg+, svn+, bzr+). Provide a URL pointing to a wheel "
                "or a package name available on a configured index."
            )

        try:
            as_req = constrain_requirement(Requirement(req), self.constrained_reqs)

            if as_req.name.endswith(".whl"):
                # This happens when the requirement is passed as a relative URL:
                # For instance, micropip.install("pkg-1.0.0-py3-none-any.whl")
                # packaging cannot distinguish this is a relative URL or a very weird wheel name ... sigh ...
                # But we want to treat it as a custom download location.
                return await self.add_requirement_from_url(req)

            return await self.add_requirement_inner(as_req)
        except InvalidRequirement:
            if not urlparse(req).path.endswith(".whl"):
                raise

        # custom download location, for instance, micropip.install("https://example.com/pkg-1.0.0-py3-none-any.whl")
        return await self.add_requirement_from_url(req)

    async def add_requirement_from_url(
        self, req: str, extras: set[str] | None = None
    ) -> None:
        wheel = WheelInfo.from_url(req)
        check_compatible(wheel.filename)
        return await self.add_wheel(wheel, extras=extras or set(), specifier="")

    def check_version_satisfied(
        self, req: Requirement, *, allow_reinstall: bool = False
    ) -> tuple[bool, str]:
        """
        Check if the installed version of a package satisfies the requirement.
        Returns True if the requirement is satisfied, False otherwise.

        Parameters
        ----------
        req
            The requirement to check.

        allow_reinstall
            If False, this function will raise exception if the package is already installed
            and the installed version does not satisfy the requirement.
        """
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

        if allow_reinstall:
            return False, ""
        else:
            raise ValueError(
                f"Requested '{req}', "
                f"but {req.name}=={ver} is already installed. "
                "If you want to reinstall the package with a different version, "
                "use micropip.install(..., reinstall=True) to force reinstall, "
                "or micropip.uninstall(...) to uninstall the package first."
            )

    async def add_requirement_inner(
        self,
        req: Requirement,
    ) -> None:
        """Add a requirement to the resolution.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        # add [extras] first, as constraints will never add them
        for e in req.extras:
            self.ctx_extras.append({"extra": e})

        req = constrain_requirement(req, self.constrained_reqs)

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
            # store all the extra values we come across during the resolution and
            # attempt the marker evaluation for all of these values. If any of the
            # evaluations return true we include the dependency.

            def eval_marker(e: dict[str, str]) -> bool:
                self.ctx.update(e)
                # need the assertion here to make mypy happy:
                # https://github.com/python/mypy/issues/4805
                assert req.marker is not None
                return req.marker.evaluate(self.ctx)

            self.ctx.update({"extra": ""})
            # The current package may have been brought into the resolution
            # without any of the optional requirement specification, but has
            # another marker, such as implementation_name. In this scenario,
            # self.ctx_extras is empty and hence the eval_marker() function
            # will not be called at all.
            if not req.marker.evaluate(self.ctx) and not any(
                eval_marker(e) for e in self.ctx_extras
            ):
                return

        # Is some version of this package is already installed?
        req.name = canonicalize_name(req.name)

        satisfied, ver = self.check_version_satisfied(
            req, allow_reinstall=self.reinstall
        )

        if satisfied:
            logger.info("Requirement already satisfied: %s (%s)", req, ver)
            return

        if req.url:
            # custom download location, for instance, micropip.install("pkg @ https://example.com/pkg-1.0.0-py3-none-any.whl")
            # in this case, we don't need to search the index_urls or pyodide lock file.
            return await self.add_requirement_from_url(req.url, extras=req.extras)

        try:
            await self._add_requirement_from_sources(req)
        except ValueError:
            self.failed.append(req)
            if not self.keep_going:
                raise

    def _sources(self) -> list[list[str] | None]:
        """
        Split ``index_urls`` into the ordered list of sources to search.

        ``None`` stands for the Pyodide lock file, and a list of URLs for package
        indexes that are queried together by :meth:`query_package`.

        If ``index_urls`` contains ``"PYODIDE"``, the lock file is searched at that
        position. Otherwise, the lock file is searched before the default index
        (PyPI), or after custom indexes as a fallback.
        """
        index_urls = (
            [self.index_urls] if isinstance(self.index_urls, str) else self.index_urls
        )

        if package_index.PYODIDE not in index_urls:
            if self.search_pyodide_lock_first:
                return [None, list(index_urls)]
            return [list(index_urls), None]

        sources: list[list[str] | None] = []
        urls: list[str] = []
        for url in index_urls:
            if url != package_index.PYODIDE:
                urls.append(url)
                continue
            if urls:
                sources.append(urls)
                urls = []
            sources.append(None)
        if urls:
            sources.append(urls)
        return sources

    async def _add_requirement_from_sources(self, req: Requirement) -> None:
        """
        Search the sources from :meth:`_sources` in order and add the requirement
        from the first one that has a matching package. Raise ``ValueError`` if
        none of them has it.
        """
        error: ValueError | None = None
        for urls in self._sources():
            if urls is None:
                if await self._add_requirement_from_pyodide_lock(req):
                    logger.debug("Resolver: package found in lock file: %r", req)
                    return
                logger.debug("Resolver: package %r not found in lock file", req)
                continue

            try:
                await self._add_requirement_from_package_index(req, urls)
                return
            except ValueError as e:
                logger.debug("Resolver: package %r not found in %r", req, urls)
                error = e

        if error is not None:
            raise error

        raise ValueError(
            f"Can't find a package that satisfies '{req}' in the Pyodide lock file. "
            "Add a package index to index_urls to look for it there as well."
        )

    async def _add_requirement_from_pyodide_lock(self, req: Requirement) -> bool:
        """
        Find requirement from pyodide-lock.json. If the requirement is found,
        add it to the package list and return True. Otherwise, return False.
        """
        lockfile = self.compat_layer.lockfile
        if lockfile is None:
            return False

        locked_package = lockfile.get(req.name)
        if locked_package and req.specifier.contains(
            locked_package.version, prereleases=True
        ):
            self.pyodide_packages.append(
                PackageMetadata(
                    name=req.name, version=locked_package.version, source="pyodide"
                )
            )
            if self.constraints and locked_package.depends:
                await self.gather_requirements(locked_package.depends)
            return True

        return False

    async def _add_requirement_from_package_index(
        self, req: Requirement, index_urls: list[str] | None = None
    ):
        """Find requirement from package index.

        If the requirement is found, add it to the package list.
        """
        metadata = await self.query_package(req.name, index_urls)

        logger.debug("Resolver: got metadata %r for requirement %r", metadata, req)

        wheel = self.find_wheel(metadata, req)

        logger.debug("Resolver: Selected wheel: %r", wheel)

        if wheel.yanked:
            yanked_reason = wheel.yanked_reason if wheel.yanked_reason else "None"
            logger.info(
                YANKED_WARNING_MESSAGE,
                wheel.name,
                str(wheel.version),
                wheel.url,
                yanked_reason,
            )

        # Maybe while we were querying the index some other branch
        # added the wheel?
        satisfied, ver = self.check_version_satisfied(
            req, allow_reinstall=self.reinstall
        )
        if satisfied:
            logger.info("Requirement already satisfied: %s (%s)", req, ver)
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
        Download a wheel, and add its dependencies to the resolution.

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

        logger.info("Collecting %s%s", wheel.name, specifier)
        logger.info("  Downloading %s", wheel.url.split("/")[-1])

        wheel_download_task = asyncio.create_task(self.download_wheel(wheel))
        if self.deps:
            # Case 1) If metadata file is available,
            #         we can gather requirements without waiting for the wheel to be downloaded.
            if wheel.pep658_metadata_available():
                try:
                    await self.download_wheel_metadata(wheel)
                except OSError:
                    # If something goes wrong while downloading the metadata,
                    # we have to wait for the wheel to be downloaded.
                    await wheel_download_task

                await asyncio.gather(
                    self.gather_requirements(wheel.requires(extras)),
                    wheel_download_task,
                )

            # Case 2) If metadata file is not available,
            #         we have to wait for the wheel to be downloaded.
            else:
                await wheel_download_task
                await self.gather_requirements(wheel.requires(extras))
        else:
            await wheel_download_task

        self.wheels.append(wheel)

    async def query_package(
        self, name: str, index_urls: list[str] | str | None = None
    ) -> ProjectInfo:
        """
        Query the package indexes in ``index_urls`` for the package ``name``.

        The indexes are tried in order, and the first one that has the package
        is used. Raises ``ValueError`` if no index has the package.
        If ``index_urls`` is not given, :attr:`index_urls` of the resolver is used.
        The special value ``"PYODIDE"`` (the Pyodide lock file) is skipped.
        """
        if index_urls is None:
            index_urls = self.index_urls
        # If not specified, prefer Simple JSON API over Simple HTML API or JSON API
        options = replace(
            self.fetch_options,
            headers={
                "accept": "application/vnd.pypi.simple.v1+json, */*;q=0.01",
                **self.fetch_options.headers,
            },
        )

        for url in package_index.project_urls(name, index_urls):
            try:
                response = await self.compat_layer.fetch(url, options)
            except Exception as e:
                logger.debug(
                    "Error fetching metadata for the package %r from (%r): %r, trying next index.",
                    name,
                    url,
                    e,
                )
                continue

            return package_index.parse_project_info(
                name, url, response.text(), response.headers
            )

        raise ValueError(
            f"Can't fetch metadata for '{name}'. "
            "Please make sure you have entered a correct package name "
            "and correctly specified index_urls (if you changed them)."
        )

    def find_wheel(self, metadata: ProjectInfo, req: Requirement) -> WheelInfo:
        """Select the wheel to install for ``req`` from the project ``metadata``."""
        return find_wheel(metadata, req)

    async def download_wheel(self, wheel: WheelInfo) -> None:
        """Download ``wheel`` (and its metadata, if not downloaded yet)."""
        if wheel.downloaded:
            return

        wheel.set_data(await self.fetch_bytes(wheel.url, wheel))

    async def download_wheel_metadata(self, wheel: WheelInfo) -> None:
        """Download the metadata of ``wheel`` separately (PEP 658), if the index provides it."""
        if not wheel.pep658_metadata_available():
            return

        wheel.set_pep658_metadata(await self.fetch_bytes(wheel.metadata_url, wheel))

    async def fetch_bytes(self, url: str, wheel: WheelInfo) -> bytes:
        """Fetch ``url``, a file that belongs to ``wheel``."""
        response = await self.compat_layer.fetch(url, self.fetch_options)
        return response.content


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

    yanked_versions: list[list[WheelInfo]] = []

    for ver in candidate_versions:
        if ver not in releases:
            warnings.warn(
                f"The package '{metadata.name}' contains an invalid version: '{ver}'. This version will be skipped",
                stacklevel=1,
            )
            continue

        wheels = list(releases[ver])

        # If the version is yanked, put it in the end of the candidate list.
        # If we can't find a wheel that satisfies the requirement,
        # install the yanked version as a last resort.
        # when the version is yanked, all wheels are yanked, so we can check only the first wheel.
        yanked = wheels and wheels[0].yanked
        if yanked:
            yanked_versions.append(wheels)
            continue

        best_wheel = _find_best_wheel(wheels)

        if best_wheel is not None:
            return best_wheel

    for wheels in yanked_versions:
        best_wheel = _find_best_wheel(wheels)

        if best_wheel is not None:
            return best_wheel

    raise ValueError(
        f"Can't find a pure Python 3 wheel for '{req}'.\n"
        f"See: {FAQ_URLS['cant_find_wheel']}\n"
        "You can use `await micropip.install(..., keep_going=True)` "
        "to get a list of all packages with missing wheels."
    )


def _find_best_wheel(wheels: Iterable[WheelInfo]) -> WheelInfo | None:
    best_wheel = None
    best_tag_index = float("infinity")
    for wheel in wheels:
        tag_index = wheel.best_tag_index
        if tag_index is not None and tag_index < best_tag_index:
            best_wheel = wheel
            best_tag_index = tag_index

    return best_wheel
