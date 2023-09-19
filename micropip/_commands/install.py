import asyncio
import importlib
from pathlib import Path

from packaging.markers import default_environment

from .. import package_index
from .._compat import loadPackage, to_js
from ..constants import FAQ_URLS
from ..logging import setup_logging
from ..transaction import Transaction


async def install(
    requirements: str | list[str],
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
    index_urls: list[str] | str | None = None,
    *,
    verbose: bool | int = False,
) -> None:
    """Install the given package and all of its dependencies.

    If a package is not found in the Pyodide repository it will be loaded from
    PyPI. Micropip can only load pure Python wheels or wasm32/emscripten wheels
    built by Pyodide.

    When used in web browsers, downloads from PyPI will be cached. When run in
    Node.js, packages are currently not cached, and will be re-downloaded each
    time ``micropip.install`` is run.

    Parameters
    ----------
    requirements :

        A requirement or list of requirements to install. Each requirement is a
        string, which should be either a package name or a wheel URI:

        - If the requirement does not end in ``.whl``, it will be interpreted as
          a package name. A package with this name must either be present
          in the Pyodide lock file or on PyPI.

        - If the requirement ends in ``.whl``, it is a wheel URI. The part of
          the requirement after the last ``/``  must be a valid wheel name in
          compliance with the `PEP 427 naming convention
          <https://www.python.org/dev/peps/pep-0427/#file-format>`_.

        - If a wheel URI starts with ``emfs:``, it will be interpreted as a path
          in the Emscripten file system (Pyodide's file system). E.g.,
          ``emfs:../relative/path/wheel.whl`` or ``emfs:/absolute/path/wheel.whl``.
          In this case, only .whl files are supported.

        - If a wheel URI requirement starts with ``http:`` or ``https:`` it will
          be interpreted as a URL.

        - In node, you can access the native file system using a URI that starts
          with ``file:``. In the browser this will not work.

    keep_going :

        This parameter decides the behavior of the micropip when it encounters a
        Python package without a pure Python wheel while doing dependency
        resolution:

        - If ``False``, an error will be raised on first package with a missing
          wheel.

        - If ``True``, the micropip will keep going after the first error, and
          report a list of errors at the end.

    deps :

        If ``True``, install dependencies specified in METADATA file for each
        package. Otherwise do not install dependencies.

    credentials :

        This parameter specifies the value of ``credentials`` when calling the
        `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__
        function which is used to download the package.

        When not specified, ``fetch()`` is called without ``credentials``.

    pre :

        If ``True``, include pre-release and development versions. By default,
        micropip only finds stable versions.

    index_urls :

        A list of URLs or a single URL to use as the package index when looking
        up packages. If None, *https://pypi.org/pypi/{package_name}/json* is used.

        - The index URL should support the
          `JSON API <https://warehouse.pypa.io/api-reference/json/>`__ .

        - The index URL may contain the placeholder {package_name} which will be
          replaced with the package name when looking up a package. If it does not
          contain the placeholder, the package name will be appended to the URL.

        - If a list of URLs is provided, micropip will try each URL in order until
          it finds a package. If no package is found, an error will be raised.

    verbose :
        Print more information about the process.
        By default, micropip is silent. Setting ``verbose=True`` will print
        similar information as pip.
    """
    logger = setup_logging(verbose)

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

    if index_urls is None:
        index_urls = package_index.INDEX_URLS[:]

    transaction = Transaction(
        ctx=ctx,
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

    if package_names:
        logger.info("Installing collected packages: " + ", ".join(package_names))

    wheel_promises = []
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

    packages = [f"{pkg.name}-{pkg.version}" for pkg in transaction.pyodide_packages] + [
        f"{pkg.name}-{pkg.version}" for pkg in transaction.wheels
    ]

    if packages:
        logger.info("Successfully installed " + ", ".join(packages))

    importlib.invalidate_caches()
