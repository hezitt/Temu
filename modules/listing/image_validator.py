import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class ImageInspectionError(ValueError):
    pass


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    format: str
    width_px: int
    height_px: int
    size_bytes: int


def inspect_image(path: Path) -> ImageInfo:
    image_path = path.expanduser().resolve()
    if not image_path.is_file():
        raise ImageInspectionError(f"Image does not exist: {image_path}")
    size_bytes = image_path.stat().st_size
    with image_path.open("rb") as stream:
        signature = stream.read(24)
        if signature.startswith(b"\x89PNG\r\n\x1a\n") and len(signature) >= 24:
            width, height = struct.unpack(">II", signature[16:24])
            return ImageInfo(image_path, "PNG", width, height, size_bytes)
        if signature[:2] == b"\xff\xd8":
            stream.seek(2)
            width, height = _jpeg_dimensions(stream)
            return ImageInfo(image_path, "JPEG", width, height, size_bytes)
    raise ImageInspectionError(f"Unsupported or invalid image file: {image_path}")


def _jpeg_dimensions(stream: BinaryIO) -> tuple[int, int]:
    while True:
        marker_start = stream.read(1)
        if not marker_start:
            break
        if marker_start != b"\xff":
            continue
        marker = stream.read(1)
        while marker == b"\xff":
            marker = stream.read(1)
        if not marker:
            break
        marker_value = marker[0]
        if marker_value in {0xD8, 0xD9}:
            continue
        length_bytes = stream.read(2)
        if len(length_bytes) != 2:
            break
        segment_length = struct.unpack(">H", length_bytes)[0]
        if segment_length < 2:
            break
        if marker_value in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            payload = stream.read(segment_length - 2)
            if len(payload) < 5:
                break
            height, width = struct.unpack(">HH", payload[1:5])
            return width, height
        stream.read(segment_length - 2)
    raise ImageInspectionError("JPEG dimensions could not be read")


def is_publishable_image_ref(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    if candidate.startswith(("http://", "https://")):
        return True
    return all(separator not in candidate for separator in ("/", "\\", ":"))
