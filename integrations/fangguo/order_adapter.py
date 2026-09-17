from pathlib import Path
from typing import Any, Protocol


class FangguoOrderAdapter(Protocol):
    """Future boundary only; Milestone 2 must not push orders to Fangguo."""

    def validate_order(self, order: dict[str, Any]) -> list[str]: ...

    def render_import_file(
        self, *, template_path: Path, orders: list[dict[str, Any]], output_path: Path
    ) -> Path: ...
