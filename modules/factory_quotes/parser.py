from typing import Any

from integrations.excel.reader import WorksheetData
from modules.factory_quotes.schemas import RawQuoteCandidate, VariantType


class FactoryQuoteLayoutError(RuntimeError):
    pass


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


class FactoryQuoteParser:
    def parse(self, worksheet: WorksheetData) -> list[RawQuoteCandidate]:
        header_index = self._find_header_row(worksheet.rows)
        candidates: list[RawQuoteCandidate] = []
        current_color: Any = None

        for zero_based_index, row in enumerate(
            worksheet.rows[header_index + 1 :], header_index + 1
        ):
            padded = [*row, None, None, None, None, None][:5]
            excel_row = zero_based_index + 1
            explicit_color = padded[0]
            if not _blank(explicit_color):
                current_color = explicit_color

            for variant_type, size_index, cost_index, source_column in (
                (VariantType.UNFRAMED, 1, 2, "C"),
                (VariantType.FRAMED, 3, 4, "E"),
            ):
                raw_size = padded[size_index]
                raw_cost = padded[cost_index]
                if _blank(explicit_color) and _blank(raw_size) and _blank(raw_cost):
                    continue

                separator_hint = (
                    _blank(explicit_color)
                    and _blank(raw_size)
                    and (raw_cost == 0 or str(raw_cost).strip() == "0")
                )
                effective_color = None if separator_hint else current_color
                candidates.append(
                    RawQuoteCandidate(
                        source_sheet=worksheet.name,
                        source_row_number=excel_row,
                        source_column=source_column,
                        variant_type=variant_type,
                        raw_color=effective_color,
                        raw_size=raw_size,
                        raw_cost=raw_cost,
                        raw_payload={
                            "excel_row": excel_row,
                            "source_column": source_column,
                            "raw_color": explicit_color,
                            "effective_color": effective_color,
                            "raw_size": raw_size,
                            "raw_cost": raw_cost,
                            "separator_hint": separator_hint,
                        },
                    )
                )

        if not candidates:
            raise FactoryQuoteLayoutError("No factory quote candidates were found")
        return candidates

    @staticmethod
    def _find_header_row(rows: list[list[Any]]) -> int:
        for index, row in enumerate(rows[:20]):
            padded = [*row, None, None, None, None][:5]
            values = [str(value).strip() if value is not None else "" for value in padded]
            if (
                "颜色" in values[0]
                and "尺寸" in values[1]
                and "价" in values[2]
                and "尺寸" in values[3]
                and "价" in values[4]
            ):
                return index
        raise FactoryQuoteLayoutError("Could not locate the color/size/price header row")
