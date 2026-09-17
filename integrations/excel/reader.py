from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class WorksheetData:
    name: str
    rows: list[list[Any]]


class WorkbookReader(Protocol):
    def read(self, file_path: Path, sheet_name: str | None = None) -> WorksheetData: ...
