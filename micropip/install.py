import asyncio
import importlib
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from packaging.markers import default_environment

from ._compat import loadPackage, to_js
from .constants import FAQ_URLS
from .logging import setup_logging
from .transaction import Transaction


async def install(
    requirements: str | list[str],
    index_urls: list[str] | str,
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
    *,
    verbose: bool | int | None = None,
) -> None:
    with setup_logging().ctx_level(verbose) as logger:

        ctx = default_environment()
        if isinstance(requirements, str):
            requirements = [requirements]

        fetch_kwargs = dict()

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
        )
        await transaction.gather_requirements(requirements)

        if transaction.failed:
            failed_requirements = ", ".join([f"'{req}'" for req in transaction.failed])
            raise ValueError(
                f"Can't find a pure Python 3 wheel for: {failed_requirements}\n"
                f"See: {FAQ_URLS['cant_find_wheel']}\n"
            )

        package_names = [pkg.name for pkg in transaction.pyodide_packages] + [
            pkg.name for pkg in transaction.wheels
        ]

        logger.debug(
            "Installing packages %r and wheels %r ",
            transaction.pyodide_packages,
            [w.filename for w in transaction.wheels],
        )
        if package_names:
            logger.info("Installing collected packages: %s", ", ".join(package_names))

        wheel_promises: list[Coroutine[Any, Any, None] | asyncio.Task[Any]] = []
        # Install built-in packages
        pyodide_packages = transaction.pyodide_packages
        if len(pyodide_packages):
            # Note: branch never happens in out-of-browser testing because in
            # that case REPODATA_PACKAGES is empty.
            wheel_promises.append(
                asyncio.ensure_future(
                    loadPackage(to_js([name for [name, _, _] in pyodide_packages]))
                )
            )

        # Now install PyPI packages
        for wheel in transaction.wheels:
            # detect whether the wheel metadata is from PyPI or from custom location
            # wheel metadata from PyPI has SHA256 checksum digest.
            wheel_promises.append(wheel.install(wheel_base))

        await asyncio.gather(*wheel_promises)

        packages = [
            f"{pkg.name}-{pkg.version}" for pkg in transaction.pyodide_packages
        ] + [f"{pkg.name}-{pkg.version}" for pkg in transaction.wheels]

        if packages:
            logger.info("Successfully installed %s", ", ".join(packages))

        importlib.invalidate_caches()
