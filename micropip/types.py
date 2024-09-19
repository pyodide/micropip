# Destribution Metadata type (PEP 658)
# None = metadata not available
# bool = metadata available, but no checksum
# dict[str, str] = metadata available with checksum
DistributionMetadata = bool | dict[str, str] | None