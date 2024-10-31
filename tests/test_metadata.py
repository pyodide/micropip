from pathlib import Path

import pytest

TEST_METADATA_DIR = Path(__file__).parent / "test_data" / "metadata"


@pytest.mark.parametrize(
    "metadata_path, extras, expected",
    [
        (
            "boto3-1.28.51-py3-none-any.whl.metadata",
            (),
            ["botocore", "jmespath", "s3transfer"],
        ),
        (
            "requests-2.31.0-py3-none-any.whl.metadata",
            (),
            ["certifi", "urllib3", "charset-normalizer", "idna"],
        ),
        (
            "requests-2.31.0-py3-none-any.whl.metadata",
            (
                "socks",
                "use_chardet_on_py3",
            ),
            ["certifi", "urllib3", "charset-normalizer", "idna", "PySocks", "chardet"],
        ),
    ],
)
def test_Metadata_requires(metadata_path, extras, expected):
    from micropip.metadata import Metadata

    metadata = (TEST_METADATA_DIR / metadata_path).read_bytes()
    m = Metadata(metadata)

    reqs = m.requires(extras)
    reqs_set = set([r.name for r in reqs])
    assert reqs_set == set(expected)


def test_Metadata_extra_invalid():
    from micropip.metadata import Metadata

    metadata = (
        TEST_METADATA_DIR / "boto3-1.28.51-py3-none-any.whl.metadata"
    ).read_bytes()
    m = Metadata(metadata)
    extras = ("invalid",)

    with pytest.raises(KeyError, match="Unknown extra"):
        m.requires(extras)


def test_Metadata_marker():
    from micropip.metadata import Metadata

    metadata = (
        TEST_METADATA_DIR / "urllib3-2.0.5-py3-none-any.whl.metadata"
    ).read_bytes()
    m = Metadata(metadata)
    extras = ("brotli", "zstd")

    reqs = m.requires(extras)
    markers = {r.name: str(r.marker) for r in reqs}

    assert "brotli" in markers
    assert (
        markers["brotli"]
        == 'platform_python_implementation == "CPython" and extra == "brotli"'
    )

    assert "zstandard" in markers
    assert markers["zstandard"] == 'extra == "zstd"'


def test_Metadata_extra_of_requires():
    from micropip.metadata import Metadata

    metadata = (
        TEST_METADATA_DIR / "boto3-1.28.51-py3-none-any.whl.metadata"
    ).read_bytes()
    m = Metadata(metadata)
    extras = ("crt",)

    reqs = m.requires(extras)
    reqs_set = {r.name: r.extras for r in reqs}

    assert "botocore" in reqs_set
    assert reqs_set["botocore"] == {"crt"}
