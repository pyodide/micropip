import functools
from importlib.metadata import Distribution
from pathlib import Path
from sysconfig import get_platform

from packaging.tags import Tag
from packaging.tags import sys_tags as sys_tags_orig
from packaging.utils import BuildTag, InvalidWheelFilename
from packaging.utils import parse_wheel_filename as parse_wheel_filename_orig
from packaging.version import InvalidVersion, Version


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
def sys_tags() -> list[Tag]:
    return list(sys_tags_orig())


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
        raise ValueError(f"Wheel filename is invalid: {filename}") from None
    except InvalidVersion:
        raise ValueError(f"Wheel version is invalid: {filename}") from None

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
