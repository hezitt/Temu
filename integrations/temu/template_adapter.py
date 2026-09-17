import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol, cast

from openpyxl import load_workbook

from core.config import ReportSettings
from modules.listing.schemas import CanonicalListingRow


class TemuTemplateError(RuntimeError):
    pass


class TemuListingAdapter(Protocol):
    def export(
        self,
        *,
        template_path: Path,
        mapping_path: Path,
        rows: list[CanonicalListingRow],
        output_path: Path,
    ) -> Path: ...


class TemuExcelTemplateAdapter:
    REQUIRED_CANONICAL_FIELDS = {
        "title",
        "sku",
        "width_cm",
        "height_cm",
        "colors_count",
        "framed",
        "main_image",
    }

    def __init__(self, reports: ReportSettings, project_root: Path) -> None:
        self.node_executable = reports.node_executable
        self.writer_script = project_root / "scripts" / "fill_temu_template.mjs"

    def validate_mapping(
        self, template_path: Path, mapping_path: Path, *, allow_test_fixture: bool = False
    ) -> dict[str, Any]:
        template = template_path.expanduser().resolve()
        mapping_file = mapping_path.expanduser().resolve()
        if not template.is_file() or template.suffix.lower() != ".xlsx":
            raise TemuTemplateError("A real Temu .xlsx template is required")
        if not mapping_file.is_file():
            raise TemuTemplateError("A reviewed Temu field mapping JSON is required")
        try:
            raw_mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise TemuTemplateError(f"Cannot read Temu mapping: {exc}") from exc
        if not isinstance(raw_mapping, dict):
            raise TemuTemplateError("Temu mapping must be a JSON object")
        mapping = cast(dict[str, Any], raw_mapping)
        allowed_platforms = {"TEMU", "TEMU_TEST_FIXTURE"} if allow_test_fixture else {"TEMU"}
        if mapping.get("platform") not in allowed_platforms:
            raise TemuTemplateError(
                "Mapping must explicitly identify platform=TEMU; Fangguo templates are not accepted"
            )
        columns = mapping.get("columns")
        if not isinstance(columns, dict):
            raise TemuTemplateError("Mapping columns must be an object")
        missing = self.REQUIRED_CANONICAL_FIELDS - set(columns)
        if missing:
            raise TemuTemplateError(
                "Temu mapping is missing canonical fields: " + ", ".join(sorted(missing))
            )
        expected_hash = mapping.get("template_sha256")
        actual_hash = hashlib.sha256(template.read_bytes()).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise TemuTemplateError("Temu template SHA-256 does not match the reviewed mapping")
        mapping["actual_template_sha256"] = actual_hash
        return mapping

    def export(
        self,
        *,
        template_path: Path,
        mapping_path: Path,
        rows: list[CanonicalListingRow],
        output_path: Path,
        allow_test_fixture: bool = False,
    ) -> Path:
        mapping = self.validate_mapping(
            template_path, mapping_path, allow_test_fixture=allow_test_fixture
        )
        if not rows:
            raise TemuTemplateError("No valid listing rows are available for export")
        payload = {
            "mapping": mapping,
            "rows": [row.model_dump(mode="json") for row in rows],
        }
        output = output_path.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="temu-template-") as temp_dir:
            payload_path = Path(temp_dir) / "payload.json"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    self.node_executable,
                    str(self.writer_script),
                    str(template_path.expanduser().resolve()),
                    str(payload_path),
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        if result.returncode != 0 or not output.is_file():
            raise TemuTemplateError(
                "Temu template export failed: " + (result.stderr.strip() or result.stdout.strip())
            )
        self._restore_sheet_visibility(template_path.expanduser().resolve(), output)
        return output

    @staticmethod
    def _restore_sheet_visibility(template_path: Path, output_path: Path) -> None:
        """Restore metadata not currently round-tripped by Artifact Tool's XLSX importer."""
        source = load_workbook(template_path, read_only=True, data_only=False)
        target = load_workbook(output_path, read_only=False, data_only=False)
        try:
            states = {sheet.title: sheet.sheet_state for sheet in source.worksheets}
            for sheet in target.worksheets:
                if sheet.title in states:
                    sheet.sheet_state = states[sheet.title]
            target.save(output_path)
        finally:
            source.close()
            target.close()
