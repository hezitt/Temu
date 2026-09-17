import hashlib
import json
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from core.config import ReportSettings
from integrations.temu.template_adapter import TemuExcelTemplateAdapter
from modules.listing.schemas import CanonicalListingRow


def test_template_adapter_preserves_sheets_format_and_writes_fields(tmp_path: Path) -> None:
    template = tmp_path / "temu-test-template.xlsx"
    workbook = Workbook()
    upload = workbook.worksheets[0]
    upload.title = "Upload"
    headers = ["Title", "SKU", "Width", "Height", "Colors", "Framed", "Main image"]
    for column, header in enumerate(headers, start=1):
        cell = upload.cell(row=3, column=column, value=header)
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    lists = workbook.create_sheet("Lists")
    lists.sheet_state = "hidden"
    lists["A1"] = "DO NOT REMOVE"
    workbook.save(template)
    template_hash = hashlib.sha256(template.read_bytes()).hexdigest()
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "platform": "TEMU_TEST_FIXTURE",
                "template_sha256": template_hash,
                "sheet_name": "Upload",
                "header_row": 3,
                "first_data_row": 4,
                "columns": {
                    "title": "A",
                    "sku": "B",
                    "width_cm": "C",
                    "height_cm": "D",
                    "colors_count": "E",
                    "framed": "F",
                    "main_image": "G",
                },
                "expected_headers": {
                    "title": "Title",
                    "sku": "SKU",
                    "width_cm": "Width",
                    "height_cm": "Height",
                    "colors_count": "Colors",
                    "framed": "Framed",
                    "main_image": "Main image",
                },
            }
        ),
        encoding="utf-8",
    )
    row = CanonicalListingRow(
        design_id="DESIGN-CAT-000001",
        factory_design_code="CAT000001",
        title="Cat - Animals - Paint by Numbers Kit",
        theme="Animals",
        product_type="PAINT_BY_NUMBERS",
        target_market="US",
        main_image="/tmp/CAT000001.jpg",
        additional_images="",
        sku="PBN-CAT000001-4050-24-U",
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        colors_count=24,
        framed=False,
        factory_cost_cny=Decimal("44"),
        shipping_cost_usd=Decimal("4"),
        unit_variable_cost_cny=Decimal("73"),
    )
    output = tmp_path / "filled.xlsx"
    adapter = TemuExcelTemplateAdapter(ReportSettings(), Path.cwd())
    adapter.export(
        template_path=template,
        mapping_path=mapping,
        rows=[row],
        output_path=output,
        allow_test_fixture=True,
    )
    loaded = load_workbook(output)
    assert loaded.sheetnames == ["Upload", "Lists"]
    assert loaded["Lists"].sheet_state == "hidden"
    assert loaded["Lists"]["A1"].value == "DO NOT REMOVE"
    assert loaded["Upload"]["A3"].fill.fgColor.rgb.endswith("1F4E78")
    assert loaded["Upload"]["A4"].value == row.title
    assert loaded["Upload"]["B4"].value == row.sku
    assert loaded["Upload"]["F4"].value == "NO"
