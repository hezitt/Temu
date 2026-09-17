from pathlib import Path


def normalize_image_path(path: Path, *, base_dir: Path | None = None) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute() and base_dir is not None:
        expanded = base_dir / expanded
    return expanded.resolve()
