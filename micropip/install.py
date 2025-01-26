import asyncio
import importlib
from pathlib import Path

from packaging.markers import default_environment

from ._compat import loadPackage, to_js
from .constants import FAQ_URLS
from .logging import setup_logging
from .package import PackageMetadata
from .transaction import Transaction
from .wheelinfo import WheelInfo


async def install(
    requirements: str | list[str],
    index_urls: list[str] | str,
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
    *,
    constraints: list[str] | None = None,
    verbose: bool | int | None = None,
) -> None:
    with setup_logging().ctx_level(verbose) as logger:

        ctx = default_environment()
        if isinstance(requirements, str):
            requirements = [requirements]

        fetch_kwargs = {}

        if credentials:
            fetch_kwargs["credentials"] = credentials

        # Note: getsitepackages is not available in a virtual environment...
        # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
        # problem is not fixed)
        from site import getsitepackages

        wheel_base = Path(getsitepackages()[0])

        transaction = Transaction(
            ctx=ctx,  # type: ignore[arg-type]
            ctx_extras=[],
            keep_going=keep_going,
            deps=deps,
            pre=pre,
            fetch_kwargs=fetch_kwargs,
            verbose=verbose,
            index_urls=index_urls,
            constraints=constraints,
        )
        await transaction.gather_requirements(requirements)

        if transaction.failed:
            failed_requirements = ", ".join([f"'{req}'" for req in transaction.failed])
            raise ValueError(
                f"Can't find a pure Python 3 wheel for: {failed_requirements}\n"
                f"See: {FAQ_URLS['cant_find_wheel']}\n"
            )

        packages_by_name: dict[str, PackageMetadata | WheelInfo] = {
            **{pkg.name: pkg for pkg in transaction.pyodide_packages},
            **{pkg.name: pkg for pkg in transaction.wheels},
        }

        logger.debug(
            "Installing packages %r and wheels %r ",
            transaction.pyodide_packages,
            [w.filename for w in transaction.wheels],
        )
        if packages_by_name:
            logger.info(
                "Installing collected packages: %s", ", ".join(packages_by_name)
            )

        wheel_tasks: dict[str, asyncio.Task[None]] = {}
        for pkg_name in packages_by_name:
            wheel_tasks[pkg_name] = _install_one(
                pkg_name,
                packages_by_name,
                transaction.dependency_graph,
                wheel_tasks,
                wheel_base,
            )

        await asyncio.gather(*wheel_tasks.values())

        packages = [
            f"{pkg.name}-{pkg.version}" for pkg in transaction.pyodide_packages
        ] + [f"{pkg.name}-{pkg.version}" for pkg in transaction.wheels]

        if packages:
            logger.info("Successfully installed %s", ", ".join(packages))

        importlib.invalidate_caches()


def _install_one(
    pkg_name: str,
    packages_by_name: dict[str, PackageMetadata | WheelInfo],
    dependency_graph: dict[str, list[str]],
    wheel_tasks: dict[str, asyncio.Task[None]],
    wheel_base: Path,
) -> asyncio.Task[None]:
    """Build a task that waits for its dependencies to install first."""

    async def _install_one_inner():
        wheel = packages_by_name.get(pkg_name)
        dependencies = [
            wheel_tasks[dependency]
            for dependency in dependency_graph.get(pkg_name, [])
            if dependency in wheel_tasks
        ]
        if dependencies:
            await asyncio.gather(*dependencies)
        if isinstance(wheel, WheelInfo):
            await wheel.install(wheel_base)
        elif isinstance(wheel, PackageMetadata):
            await asyncio.ensure_future(loadPackage(to_js(wheel.name)))

    return asyncio.Task(_install_one_inner(), name=pkg_name)
