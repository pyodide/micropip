"""
A module to define micropip custom Exceptions.
"""


class UnsupportedContentTypeError(Exception):
    """raise when selecting a parser for current index

    This is raise if the current content type is not recognized.
    """


class NoCompatibleWheelError(Exception):
    """
    This is raised when a package is found but have no wheel compatible with
    current pyodide.
    """


class PackageNotFoundOnAnyIndexError(Exception):
    """
    This is raised if current package was not found on any of the currently
    listed index.
    """
