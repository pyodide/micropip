import asyncio
import importlib.metadata
import logging
import warnings
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from urllib.parse import urlparse

from . import package_index
from ._compat import REPODATA_PACKAGES
from ._utils import (
    best_compatible_tag_index,
    check_compatible,
    constrain_requirement,
    validate_constraints,
)
from ._vendored.packaging.src.packaging.requirements import (
    InvalidRequirement,
    Requirement,
)
from ._vendored.packaging.src.packaging.utils import canonicalize_name
from .constants import FAQ_URLS
from .package import PackageMetadata
from .package_index import ProjectInfo
from .wheelinfo import WheelInfo

logger = logging.getLogger("micropip")


@dataclass
class Transaction:
    ctx: dict[str, str]
    ctx_extras: list[dict[str, str]]
    keep_going: bool
    deps: bool
    pre: bool
    fetch_kwargs: dict[str, str]
    index_urls: list[str] | str

    locked: dict[str, PackageMetadata] = field(default_factory=dict)
    wheels: list[WheelInfo] = field(default_factory=list)
    pyodide_packages: list[PackageMetadata] = field(default_factory=list)
    failed: list[Requirement] = field(default_factory=list)

    verbose: bool | int | None = None
    constraints: list[str] | None = None
    reinstall: bool = False

    def __post_init__(self) -> None:
        # If index_urls is None, pyodide-lock.json have to be searched first.
        # TODO: when PyPI starts to support hosting WASM wheels, this might be deleted.
        self.search_pyodide_lock_first = (
            self.index_urls == package_index.DEFAULT_INDEX_URLS
        )

        self.constrained_reqs, messages = validate_constraints(
            self.constraints, self.ctx
        )

        if self.verbose and messages:
            for constraint, msg in messages.items():
                logger.info("Transaction: constraint %s discarded: %s", constraint, msg)

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

        try:
            as_req = constrain_requirement(Requirement(req), self.constrained_reqs)
        except InvalidRequirement:
            as_req = None

        if as_req:
            if as_req.name and len(as_req.specifier):
                return await self.add_requirement_inner(as_req)
            if as_req.url:
                req = as_req.url

        if urlparse(req).path.endswith(".whl"):
            # custom download location
            wheel = WheelInfo.from_url(req)
            check_compatible(wheel.filename)
            return await self.add_wheel(wheel, extras=set(), specifier="")

        return await self.add_requirement_inner(Requirement(req))

    def check_version_satisfied(self, req: Requirement, *, allow_reinstall: bool = False) -> tuple[bool, str]:
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
        """Add a requirement to the transaction.

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

        try:
            if self.search_pyodide_lock_first:
                if await self._add_requirement_from_pyodide_lock(req):
                    logger.debug("Transaction: package found in lock file: %r", req)
                    return

                await self._add_requirement_from_package_index(req)
            else:
                try:
                    await self._add_requirement_from_package_index(req)
                except ValueError:
                    logger.debug(
                        "Transaction: package %r not found in index, will search lock file",
                        req,
                    )

                    # If the requirement is not found in package index,
                    # we still have a chance to find it from pyodide lockfile.
                    if not await self._add_requirement_from_pyodide_lock(req):
                        logger.debug(
                            "Transaction: package %r not found in lock file", req
                        )

                        raise
        except ValueError:
            self.failed.append(req)
            if not self.keep_going:
                raise

    async def _add_requirement_from_pyodide_lock(self, req: Requirement) -> bool:
        """
        Find requirement from pyodide-lock.json. If the requirement is found,
        add it to the package list and return True. Otherwise, return False.
        """
        locked_package = REPODATA_PACKAGES.get(req.name)
        if locked_package and req.specifier.contains(
            REPODATA_PACKAGES[req.name]["version"], prereleases=True
        ):
            version = locked_package["version"]
            self.pyodide_packages.append(
                PackageMetadata(name=req.name, version=str(version), source="pyodide")
            )
            if self.constraints and locked_package["depends"]:
                await self.gather_requirements(locked_package["depends"])
            return True

        return False

    async def _add_requirement_from_package_index(self, req: Requirement):
        """Find requirement from package index.

        If the requirement is found, add it to the package list.
        """
        metadata = await package_index.query_package(
            req.name,
            self.index_urls,
            self.fetch_kwargs,
        )

        logger.debug("Transaction: got metadata %r for requirement %r", metadata, req)

        wheel = find_wheel(metadata, req)

        logger.debug("Transaction: Selected wheel: %r", wheel)

        # Maybe while we were downloading pypi_json some other branch
        # installed the wheel?
        satisfied, ver = self.check_version_satisfied(
            req, allow_reinstall=self.reinstall
        )
        if satisfied:
            logger.info("Requirement already satisfied: %s (%s)", req, ver)

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

        logger.info("Collecting %s%s", wheel.name, specifier)
        logger.info("  Downloading %s", wheel.url.split("/")[-1])

        wheel_download_task = asyncio.create_task(wheel.download(self.fetch_kwargs))
        if self.deps:
            # Case 1) If metadata file is available,
            #         we can gather requirements without waiting for the wheel to be downloaded.
            if wheel.pep658_metadata_available():
                try:
                    await wheel.download_pep658_metadata(self.fetch_kwargs)
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

        wheels = releases[ver]
        for wheel in wheels:
            tag_index = best_compatible_tag_index(wheel.tags)
            if tag_index is not None and tag_index < best_tag_index:
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
