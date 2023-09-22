"""
This is a stripped down version of pip._vendor.pkg_resources.DistInfoDistribution
"""
from pathlib import Path
from packaging.requirements import Requirement
import re
from collections.abc import Sequence 

def safe_extra(extra):
    """Convert an arbitrary string to a standard 'extra' name

    Any runs of non-alphanumeric characters are replaced with a single '_',
    and the result is always lowercased.
    """
    return re.sub("[^A-Za-z0-9.-]+", "_", extra).lower()


class Metadata:
    """
    Represents a metadata file in a wheel
    """
    REQUIRES_DIST = "Requires-Dist:"
    PROVIDES_EXTRA = "Provides-Extra:"

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.deps = self._compute_dependencies()

    def _parse_requirement(self, line: str) -> Requirement:
        line = line[len(self.REQUIRES_DIST):]
        if " #" in line:
            line = line[: line.find(" #")]
        
        return Requirement(line.strip())

    def _compute_dependencies(self) -> dict[str, frozenset[str]]:
        """
        Compute the dependencies of the metadata file
        """
        deps: dict[str, frozenset[str]] = {}
        reqs: list[Requirement] = []
        extras: list[str] = []

        def reqs_for_extra(extra: str) -> Requirement:
            for req in reqs:
                if not req.marker or req.marker.evaluate({"extra": extra}):
                    yield req

        lines = self.path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if line.startswith(self.REQUIRES_DIST):
                reqs.append(self._parse_requirement(line))
            elif line.startswith(self.PROVIDES_EXTRA):
                extras.append(line[len(self.PROVIDES_EXTRA):].strip())

        deps[None] = frozenset(reqs_for_extra(None))
        for extra in extras:
            deps[safe_extra(extra)] = frozenset(reqs_for_extra(extra)) - deps[None]

        return deps
    
    def requires(self, extras: Sequence[str]=()) -> list[Requirement]:
        """List of Requirements needed for this distro if `extras` are used"""
        deps = []
        deps.extend(self.deps.get(None, ()))
        for ext in extras:
            try:
                deps.extend(self.deps[safe_extra(ext)])
            except KeyError:
                raise KeyError(f"Unknown extra {ext!r}")
        return deps
    