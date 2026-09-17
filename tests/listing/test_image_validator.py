import struct
from pathlib import Path

import pytest

from modules.listing.image_validator import (
    ImageInspectionError,
    inspect_image,
    is_publishable_image_ref,
)


def test_inspect_image_reads_png_dimensions_without_image_library(tmp_path: Path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 1200, 1200))

    info = inspect_image(image)

    assert info.format == "PNG"
    assert (info.width_px, info.height_px) == (1200, 1200)


def test_inspect_image_rejects_unknown_format(tmp_path: Path) -> None:
    image = tmp_path / "sample.bin"
    image.write_bytes(b"not-an-image")
    with pytest.raises(ImageInspectionError):
        inspect_image(image)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://cdn.example.com/image.jpg", True),
        ("TEMU_ASSET_123", True),
        ("/Users/example/image.jpg", False),
        ("", False),
    ],
)
def test_publishable_image_refs_must_be_urls_or_opaque_ids(value: str, expected: bool) -> None:
    assert is_publishable_image_ref(value) is expected
