from dataclasses import dataclass

@dataclass
class PackageIndexFiles:
    filename: str  # Name of the file
    url: str # URL to download the file
    version: str # Version of the package
    sha256: str # SHA256 hash of the file
    size: int | None = None # Size of the file in bytes, if available (PEP 700)

@dataclass
class PackageIndex:
    """
    This class stores common metadata that can be obtained from different APIs (JSON, Simple)
    provided by PyPI. Responses received from PyPI or other package indexes that support the
    same APIs must be converted to this class before being processed by micropip.
    """

    name: str  # Name of the package
    versions: list[str] | None  # List of versions available, if available (PEP 700)

    # List of files available for the package, sorted in ascending order by version
    # Note that a same version may have multiple files (e.g. source distribution, wheel)
    # and this list may contain non-Pyodide compatible files (e.g. binary wheels or source distributions)
    # so it is the responsibility of the caller to filter the list and find the best file
    files: list[PackageIndexMetadataFiles] 

    @staticmethod
    def from_json_api(data: dict) -> "PackageIndexMetadata":
        """
        Converts from JSON API response

        https://warehouse.pypa.io/api-reference/json.html
        """

        name = data["info"]["name"]
        releases = data["releases"]
        versions = list(releases.keys())

        files = []
        for version, fileinfo in releases.items():
            for file in fileinfo:
                files.append(
                    PackageIndexMetadataFiles(
                        filename=file["filename"],
                        url=file["url"],
                        version=version,
                        sha256=file["digests"]["sha256"],
                        size=file["size"],
                    )
                )
            
        return PackageIndexMetadata(
            name=name,
            versions=versions,
            files=files,
        )

    
    # @staticmethod
    # def from_simple_api(data: dict) -> "PackageIndexMetadata":
    #     """
    #     Converts from Simple API response

    #     https://peps.python.org/pep-0503/
    #     https://peps.python.org/pep-0691/
    #     """

    #     raise NotImplementedError("Simple API is not supported yet")
