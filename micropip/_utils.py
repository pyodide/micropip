from importlib.metadata import Distribution
from pathlib import Path


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


def importlib_distribution(distribution_name) -> Distribution:
    """
    This is a wrapper around importlib.metadata.distribution(),
    we need to wrap it because we need to mock it in tests.
    """
    from importlib.metadata import distribution

    return distribution(distribution_name)


def importlib_distributions() -> list[Distribution]:
    """
    This is a wrapper around importlib.metadata.distributions(),
    we need to wrap it because we need to mock it in tests.
    """
    from importlib.metadata import distributions

    return list(distributions())


def importlib_version(distibution_name: str) -> str:
    """
    This is a wrapper around importlib.metadata.version(),
    we need to wrap it because we need to mock it in tests.
    """
    from importlib.metadata import version

    return version(distibution_name)
