from micropip.freeze import freeze_lockfile

from .._compat import REPODATA_INFO, REPODATA_PACKAGES


def freeze() -> str:
    return freeze_lockfile(REPODATA_PACKAGES, REPODATA_INFO)
