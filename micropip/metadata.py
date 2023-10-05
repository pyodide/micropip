"""
This is a stripped down version of pip._vendor.pkg_resources.DistInfoDistribution
"""
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def safe_name(name):
    """Convert an arbitrary string to a standard distribution name

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.
    """
    return re.sub("[^A-Za-z0-9.]+", "-", name)


def safe_extra(extra):
    """Convert an arbitrary string to a standard 'extra' name

    Any runs of non-alphanumeric characters are replaced with a single '_',
    and the result is always lowercased.
    """
    return re.sub("[^A-Za-z0-9.-]+", "_", extra).lower()


# Vendored from pip
class UnsupportedWheel(Exception):
    """Unsupported wheel."""


def wheel_dist_info_dir(source: zipfile.ZipFile, name: str) -> str:
    """Returns the name of the contained .dist-info directory.
    Raises UnsupportedWheel if not found, >1 found, or it doesn't match the
    provided name.
    """
    # Zip file path separators must be /
    subdirs = {p.split("/", 1)[0] for p in source.namelist()}

    info_dirs = [s for s in subdirs if s.endswith(".dist-info")]

    if not info_dirs:
        raise UnsupportedWheel(f".dist-info directory not found in wheel {name!r}")

    if len(info_dirs) > 1:
        raise UnsupportedWheel(
            "multiple .dist-info directories found in wheel {!r}: {}".format(
                name, ", ".join(info_dirs)
            )
        )

    info_dir = info_dirs[0]

    info_dir_name = canonicalize_name(info_dir)
    canonical_name = canonicalize_name(name)
    if not info_dir_name.startswith(canonical_name):
        raise UnsupportedWheel(
            f".dist-info directory {info_dir!r} does not start with {canonical_name!r}"
        )

    return info_dir


class Metadata:
    """
    Represents a metadata file in a wheel
    """

    PKG_INFO = "METADATA"
    REQUIRES_DIST = "Requires-Dist:"
    PROVIDES_EXTRA = "Provides-Extra:"

    def __init__(self, metadata: Path | zipfile.Path | bytes):
        self.metadata: list[str] = []

        if isinstance(metadata, Path | zipfile.Path):
            self.metadata = metadata.read_text(encoding="utf-8").splitlines()
        elif isinstance(metadata, bytes):
            self.metadata = metadata.decode("utf-8").splitlines()

        self.deps = self._compute_dependencies()

    def _parse_requirement(self, line: str) -> Requirement:
        line = line[len(self.REQUIRES_DIST) :]
        if " #" in line:
            line = line[: line.find(" #")]

        return Requirement(line.strip())

    def _compute_dependencies(self) -> dict[str | None, frozenset[Requirement]]:
        """
        Compute the dependencies of the metadata file
        """
        deps: dict[str | None, frozenset[Requirement]] = {}
        reqs: list[Requirement] = []
        extras: list[str] = []

        def reqs_for_extra(extra: str | None) -> Iterable[Requirement]:
            environment = {"extra": extra} if extra else None
            for req in reqs:
                if not req.marker or req.marker.evaluate(environment):
                    yield req

        for line in self.metadata:
            if line.startswith(self.REQUIRES_DIST):
                reqs.append(self._parse_requirement(line))
            elif line.startswith(self.PROVIDES_EXTRA):
                extras.append(line[len(self.PROVIDES_EXTRA) :].strip())

        deps[None] = frozenset(reqs_for_extra(None))
        for extra in extras:
            deps[safe_extra(extra)] = frozenset(reqs_for_extra(extra)) - deps[None]

        return deps

    def requires(self, extras: Iterable[str] = ()) -> list[Requirement]:
        """List of Requirements needed for this distro if `extras` are used"""
        deps: list[Requirement] = []

        deps.extend(self.deps.get(None, ()))
        for ext in extras:
            try:
                deps.extend(self.deps[safe_extra(ext)])
            except KeyError:
                raise KeyError(f"Unknown extra {ext!r}") from None
        return deps
