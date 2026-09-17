from integrations.excel.reader import WorksheetData
from modules.factory_quotes.parser import FactoryQuoteParser
from modules.factory_quotes.schemas import VariantType


def test_parser_expands_unframed_and_framed_columns() -> None:
    worksheet = WorksheetData(
        name="Sheet1",
        rows=[
            ["工厂"],
            ["颜色", "画芯", None, "框画", None],
            ["颜色", "尺寸", "未包邮价", "尺寸", "未包邮价"],
            ["24色", "40*50cm/16*20inch", 44, "40*50cm/16*20inch", 65],
            [None, None, 0, None, 0],
        ],
    )

    candidates = FactoryQuoteParser().parse(worksheet)

    assert len(candidates) == 4
    assert candidates[0].variant_type is VariantType.UNFRAMED
    assert candidates[0].source_row_number == 4
    assert candidates[1].variant_type is VariantType.FRAMED
    assert candidates[2].raw_payload["separator_hint"] is True
