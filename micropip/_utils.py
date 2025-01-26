import functools
import json
from importlib.metadata import Distribution
from pathlib import Path
from sysconfig import get_config_var, get_platform

from packaging.requirements import InvalidRequirement, Requirement
from packaging.tags import Tag
from packaging.tags import sys_tags as sys_tags_orig
from packaging.utils import BuildTag, InvalidWheelFilename, canonicalize_name
from packaging.utils import parse_wheel_filename as parse_wheel_filename_orig
from packaging.version import InvalidVersion, Version

from ._compat import REPODATA_PACKAGES


def get_dist_info(dist: Distribution) -> Path:
    """
    Get the .dist-info directory of a distribution.
    """
    return dist._path  # type: ignore[attr-defined]


def get_root(dist: Distribution) -> Path:
    """
    Get the root directory where a package is installed.
    This is normally the site-packages directory.
    """
    return get_dist_info(dist).parent


def get_files_in_distribution(dist: Distribution) -> set[Path]:
    """
    Get a list of files in a distribution, using the metadata.

    Parameters
    ----------
    dist
        Distribution to get files from.

    Returns
    -------
    A list of files in the distribution.
    """

    root = get_root(dist)
    dist_info = get_dist_info(dist)

    files_to_remove = set()
    pkg_files = dist.files or []
    metadata_files = dist_info.glob("*")

    for file in pkg_files:
        abspath = (root / file).resolve()
        files_to_remove.add(abspath)

    # Also add all files in the .dist-info directory.
    # Since micropip adds some extra files there, we need to remove them too.
    files_to_remove.update(metadata_files)

    return files_to_remove


@functools.cache
def sys_tags() -> tuple[Tag, ...]:
    new_tags = []
    abi_version = get_config_var("PYODIDE_ABI_VERSION")
    pyodide_platform_tag = f"pyodide_{abi_version}_wasm32"
    for tag in sys_tags_orig():
        if "emscripten" in tag.platform:
            new_tags.append(Tag(tag.interpreter, tag.abi, pyodide_platform_tag))
        new_tags.append(tag)
    return tuple(new_tags)


@functools.cache
def parse_wheel_filename(
    filename: str,
) -> tuple[str, Version, BuildTag, frozenset[Tag]]:
    return parse_wheel_filename_orig(filename)


# TODO: Move these helper functions back to WheelInfo
def parse_version(filename: str) -> Version:
    return parse_wheel_filename(filename)[1]


def parse_tags(filename: str) -> frozenset[Tag]:
    return parse_wheel_filename(filename)[3]


def best_compatible_tag_index(tags: frozenset[Tag]) -> int | None:
    """Get the index of the first tag in ``packaging.tags.sys_tags()`` that a wheel has.

    Since ``packaging.tags.sys_tags()`` is sorted from most specific ("best") to most
    general ("worst") compatibility, this index douples as a priority rank: given two
    compatible wheels, the one whose best index is closer to zero should be installed.

    Parameters
    ----------
    tags
        The tags to check.

    Returns
    -------
    The index, or ``None`` if this wheel has no compatible tags.
    """
    for index, tag in enumerate(sys_tags()):
        if tag in tags:
            return index
    return None


def is_package_compatible(filename: str) -> bool:
    """
    Check if a package is compatible with the current platform.

    Parameters
    ----------
    filename
        Filename of the package to check.
    """

    if not filename.endswith(".whl"):
        return False

    if filename.endswith("py3-none-any.whl"):
        return True

    try:
        tags = parse_tags(filename)
    except (InvalidVersion, InvalidWheelFilename):
        return False

    return best_compatible_tag_index(tags) is not None


def check_compatible(filename: str) -> None:
    """
    Check if a package is compatible with the current platform.
    If not, raise an exception with a error message that explains why.
    """
    compatible = is_package_compatible(filename)
    if compatible:
        return

    # Not compatible, now we need to figure out why.

    try:
        tags = parse_tags(filename)
    except InvalidWheelFilename:
        raise ValueError(f"Wheel filename is invalid: {filename!r}") from None
    except InvalidVersion:
        raise ValueError(f"Wheel version is invalid: {filename!r}") from None

    tag: Tag = next(iter(tags))
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
    for tag in tags:
        if tag.abi in abis:
            abi_incompatible = False
        break
    if abi_incompatible:
        abis_string = ",".join({tag.abi for tag in tags})
        raise ValueError(
            f"Wheel abi '{abis_string}' is not supported. Supported abis are 'abi3' and 'cp{version}'."
        )

    raise ValueError(f"Wheel interpreter version '{tag.interpreter}' is not supported.")


def fix_package_dependencies(
    package_name: str, *, extras: list[str | None] | None = None
) -> None:
    """Check and fix the list of dependencies for this package

    If you have manually installed a package and dependencies from wheels,
    the dependencies will not be correctly setup in the package list
    or the pyodide lockfile generated by freezing. This method checks
    if the dependencies are correctly set in the package list and will
    add missing dependencies.

    Parameters
    ----------
    package_name (string):
        The name of the package to check.

    extras (list):
        List of extras for this package.

    """
    if package_name in REPODATA_PACKAGES:
        # don't check things that are in original repository
        return

    dist = Distribution.from_name(package_name)

    package_requires = dist.requires
    if package_requires is None:
        # no dependencies - we're good to go
        return

    url = dist.read_text("PYODIDE_URL")

    # If it wasn't installed with micropip / pyodide, then we
    # can't do anything with it.
    if url is None:
        return

    # Get current list of pyodide requirements
    requires = dist.read_text("PYODIDE_REQUIRES")

    if requires:
        depends = json.loads(requires)
    else:
        depends = []

    if extras is None:
        extras = [None]
    else:
        extras = extras + [None]
    for r in package_requires:
        req = Requirement(r)
        req_extras = req.extras
        req_marker = req.marker
        req_name = canonicalize_name(req.name)
        needs_requirement = False
        if req_marker is not None:
            for e in extras:
                if req_marker.evaluate(None if e is None else {"extra": e}):
                    needs_requirement = True
                    break
        else:
            needs_requirement = True

        if needs_requirement:
            fix_package_dependencies(req_name, extras=list(req_extras))

            if req_name not in depends:
                depends.append(req_name)

    # write updated depends to PYODIDE_DEPENDS
    (get_dist_info(dist) / "PYODIDE_REQUIRES").write_text(
        json.dumps(sorted(x for x in depends))
    )


def validate_constraints(
    constraints: list[str] | None,
    environment: dict[str, str] | None = None,
) -> tuple[dict[str, Requirement], dict[str, list[str]]]:
    """Build a validated ``Requirement`` dictionary from raw constraint strings.

    Parameters
    ----------
    constraints (list):
        A list of PEP-508 dependency specs, expected to contain both a package
        name and at least one specififier.

    environment (optional dict):
        The markers for the current environment, such as OS, Python implementation.
        If ``None``, the current execution environment will be used.

    Returns
    -------
        A 2-tuple of:
        - a dictionary of ``Requirement`` objects, keyed by canonical name
        - a dictionary of message strings, keyed by constraint
    """
    constrained_reqs: dict[str, Requirement] = {}
    ignore_messages: dict[str, list[str]] = {}

    for raw_constraint in constraints or []:
        constraint_messages: list[str] = []

        try:
            req = Requirement(raw_constraint)
            req.name = canonicalize_name(req.name)
        except InvalidRequirement as err:
            ignore_messages[raw_constraint] = [f"failed to parse: {err}"]
            continue

        if req.extras:
            constraint_messages.append("may not provide [extras]")

        if not (req.url or len(req.specifier)):
            constraint_messages.append("no version or URL")

        if req.marker and not req.marker.evaluate(environment):
            constraint_messages.append(f"not applicable: {req.marker}")

        if constraint_messages:
            ignore_messages[raw_constraint] = constraint_messages
        elif req.name in constrained_reqs:
            ignore_messages[raw_constraint] = [
                f"updated existing constraint for {req.name}"
            ]
            constrained_reqs[req.name] = constrain_requirement(req, constrained_reqs)
        else:
            constrained_reqs[req.name] = req

    return constrained_reqs, ignore_messages


def constrain_requirement(
    requirement: Requirement, constrained_requirements: dict[str, Requirement]
) -> Requirement:
    """Refine or replace a requirement from a set of constraints.

    Parameters
    ----------
    requirement (list):
        A list of PEP-508 dependency specs, expected to contain both a package
        name and at least one speicifier.

    Returns
    -------
        A 2-tuple of:
        - a dictionary of ``Requirement`` objects, keyed by canonical name
        - a dictionary of messages strings, keyed by constraint
    """
    # URLs cannot be merged
    if requirement.url:
        return requirement

    as_constrained = constrained_requirements.get(canonicalize_name(requirement.name))

    if as_constrained:
        if as_constrained.url:
            requirement = as_constrained
        else:
            requirement.specifier = requirement.specifier & as_constrained.specifier

    return requirement
