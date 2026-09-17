import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core.config import ReportSettings


class ListingValidationReportError(RuntimeError):
    pass


class ListingValidationWriter:
    def __init__(self, reports: ReportSettings, project_root: Path) -> None:
        self.node_executable = reports.node_executable
        self.writer_script = project_root / "scripts" / "render_listing_validation.mjs"

    def write(self, payload: dict[str, Any], output_path: Path) -> Path:
        output = output_path.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="listing-validation-") as temp_dir:
            payload_path = Path(temp_dir) / "payload.json"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result = subprocess.run(
                [self.node_executable, str(self.writer_script), str(payload_path), str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
        if result.returncode != 0 or not output.is_file():
            raise ListingValidationReportError(
                "Listing validation report failed: "
                + (result.stderr.strip() or result.stdout.strip())
            )
        return output
