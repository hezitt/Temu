from decimal import Decimal
from typing import Any

from models.enums import VariantType
from modules.fulfillment.packaging_parser import parse_packaging_tables
from modules.fulfillment.weight_parser import parse_weight_rows


def test_packaging_parser_uses_source_table_values() -> None:
    tables = [
        [
            ["盒子规格", "适配产品尺寸（cm）", "颜料色数≤24色", "颜料色数＞24色"],
            ["无框小盒 48*8*5.5cm", "30*30、30*40", "每盒≤ 2件", "每盒≤ 1件"],
        ],
        [
            ["盒子规格", "适配产品尺寸", "装盒数量"],
            ["43*31*4cm（3040盒子）", "20*30、30*40", "1件/盒（不分色数）"],
        ],
    ]
    records = parse_packaging_tables(tables, source="packing.docx", source_hash="a" * 64)
    assert len(records) == 6
    assert records[0].box_length_cm == Decimal("48")
    assert records[0].max_units_per_box == 2
    assert records[-1].variant_type is VariantType.FRAMED


def test_weight_parser_forward_fills_color_groups_and_skips_no_quote() -> None:
    rows: list[list[Any]] = [
        ["颜色数量", "画芯", None, None, "带框（内框）", None, None],
        [None, "产品尺寸", "包装尺寸", "商品重量", "产品尺寸", "包装尺寸", "商品重量"],
        ["24色", "40*50cm/16*20inch", "55*8*5.5cm", "399g", "40*50cm", "53*41*4cm", "668g"],
        [None, "40*60cm/16*24inch", "55*8*5.5cm", "400g", "/", "/", "/"],
    ]
    records = parse_weight_rows(rows, source="weights.xls", source_hash="b" * 64)
    assert len(records) == 3
    assert records[0].weight == Decimal("399")
    assert records[1].variant_type is VariantType.FRAMED
    assert records[2].colors_count == 24
