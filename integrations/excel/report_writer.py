import json
import subprocess
import tempfile
from pathlib import Path

from core.config import Settings
from modules.factory_quotes.schemas import ImportResult


class FactoryQuoteReportError(RuntimeError):
    pass


class FactoryQuoteReportWriter:
    def __init__(self, settings: Settings) -> None:
        self.node_executable = settings.reports.node_executable
        self.script_path = (
            Path(__file__).resolve().parents[2] / "scripts" / "render_factory_quote_report.mjs"
        )

    def write(self, result: ImportResult, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump(mode="json")
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=output_path.parent,
            delete=False,
        ) as payload_file:
            json.dump(payload, payload_file, ensure_ascii=False)
            payload_path = Path(payload_file.name)

        try:
            completed = subprocess.run(
                [
                    self.node_executable,
                    str(self.script_path),
                    str(payload_path),
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                error = completed.stderr.strip() or completed.stdout.strip()
                raise FactoryQuoteReportError(f"Validation report generation failed: {error}")
        except OSError as exc:
            raise FactoryQuoteReportError(
                f"Cannot run validation report renderer {self.node_executable!r}: {exc}"
            ) from exc
        finally:
            payload_path.unlink(missing_ok=True)
