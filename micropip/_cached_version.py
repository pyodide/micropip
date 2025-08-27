from ._vendored.packaging.src.packaging.version import Version


class CachedVersion(Version):
    """This class is a subclass of Version with a lazily cached string representation for performance."""

    __slots__ = ("_cached_str",)

    def __init__(self, version: str) -> None:
        super().__init__(version)
        self._cached_str = None

    def __str__(self) -> str:
        if self._cached_str is None:
            self._cached_str = super().__str__()
        return self._cached_str

    @classmethod
    def from_version(cls, version: Version) -> "CachedVersion":
        """Helper method to create a CachedVersion from an existing Version object."""
        if isinstance(version, cls):
            return version
        instance = cls.__new__(cls)
        instance._version = version._version
        instance._key = version._key
        instance._cached_str = None
        return instance

    def __repr__(self) -> str:
        """A representation of the CachedVersion that shows all internal state.

        >>> CachedVersion('1.0.0')
        <CachedVersion('1.0.0')>
        """

        return f"<CachedVersion('{self}')>"
