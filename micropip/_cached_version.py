from ._vendored.packaging.src.packaging.version import Version, InvalidVersion

__all__ = ["CachedVersion", "parse_cached_version", "InvalidVersion"]


class CachedVersion(Version):
    """This class is a subclass of Version with cached hash and string representations for performance.
    """
    
    __slots__ = ('_cached_hash', '_cached_str')
    
    def __init__(self, version: str) -> None:
        super().__init__(version)
        
        # Cache expensive computations
        self._cached_hash = hash(self._key)
        self._cached_str = super().__str__()
    
    def __hash__(self) -> int:
        return self._cached_hash
    
    def __str__(self) -> str:
        return self._cached_str
    
    def __repr__(self) -> str:
        """A representation of the CachedVersion that shows all internal state.

        >>> CachedVersion('1.0.0')
        <CachedVersion('1.0.0')>
        """

        return f"<CachedVersion('{self}')>"


def parse_cached_version(version_str: str) -> CachedVersion:
    """Parse version string into CachedVersion object.
    Parameters
    ----------
    version_str: str
        Version string to parse (e.g., "1.2.3", "2.0.0a1")
    Returns
    -------
    CachedVersion object
    """
    return CachedVersion(version_str)
