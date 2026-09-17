from collections import defaultdict
from decimal import Decimal
from statistics import median

from modules.factory_quotes.schemas import (
    IssueCode,
    NormalizedQuote,
    Severity,
    ValidationIssue,
    VariantType,
)


def _warning(code: IssueCode, message: str) -> ValidationIssue:
    return ValidationIssue(severity=Severity.WARNING, issue_code=code, message=message)


class FactoryQuoteAnomalyDetector:
    def __init__(
        self,
        suspicious_low_ratio: float,
        size_inversion_ratio: float,
        color_inversion_ratio: float,
    ) -> None:
        self.suspicious_low_ratio = Decimal(str(suspicious_low_ratio))
        self.size_inversion_ratio = Decimal(str(size_inversion_ratio))
        self.color_inversion_ratio = Decimal(str(color_inversion_ratio))

    def detect(self, records: list[NormalizedQuote]) -> list[NormalizedQuote]:
        comparable = [record for record in records if record.is_importable]
        self._detect_duplicates(comparable)
        self._detect_framed_relationships(comparable)
        self._detect_color_inversions(comparable)
        self._detect_size_inversions(comparable)
        return records

    @staticmethod
    def _detect_duplicates(records: list[NormalizedQuote]) -> None:
        grouped: dict[tuple[object, ...], list[NormalizedQuote]] = defaultdict(list)
        for record in records:
            if record.business_key is not None:
                grouped[record.business_key].append(record)
        for duplicates in grouped.values():
            if len(duplicates) < 2:
                continue
            for record in duplicates:
                record.add_issue(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        issue_code=IssueCode.DUPLICATE_QUOTE,
                        message="同一文件中出现重复的供应商规格报价。",
                    )
                )

    def _detect_framed_relationships(self, records: list[NormalizedQuote]) -> None:
        grouped: dict[tuple[object, ...], dict[VariantType, NormalizedQuote]] = defaultdict(dict)
        for record in records:
            if record.unit_cost is None:
                continue
            key = (record.product_type, record.colors_count, record.width_cm, record.height_cm)
            grouped[key][record.variant_type] = record

        for variants in grouped.values():
            framed = variants.get(VariantType.FRAMED)
            unframed = variants.get(VariantType.UNFRAMED)
            if framed is None or unframed is None:
                continue
            assert framed.unit_cost is not None and unframed.unit_cost is not None
            if framed.unit_cost < unframed.unit_cost:
                framed.add_issue(
                    _warning(
                        IssueCode.FRAMED_LOWER_THAN_UNFRAMED,
                        "框画报价低于同规格画芯报价，请人工确认。",
                    )
                )
            if framed.unit_cost < unframed.unit_cost * self.suspicious_low_ratio:
                framed.add_issue(
                    _warning(
                        IssueCode.SUSPICIOUSLY_LOW_COST,
                        "报价显著低于同规格可比报价，但保留原始值。",
                    )
                )

        same_variant_size: dict[tuple[object, ...], list[NormalizedQuote]] = defaultdict(list)
        for record in records:
            if record.unit_cost is not None:
                size_variant_key = (
                    record.product_type,
                    record.width_cm,
                    record.height_cm,
                    record.variant_type,
                )
                same_variant_size[size_variant_key].append(record)
        for peers in same_variant_size.values():
            if len(peers) < 3:
                continue
            peer_median = Decimal(str(median([peer.unit_cost for peer in peers if peer.unit_cost])))
            for record in peers:
                assert record.unit_cost is not None
                if record.unit_cost < peer_median * self.suspicious_low_ratio:
                    record.add_issue(
                        _warning(
                            IssueCode.SUSPICIOUSLY_LOW_COST,
                            "报价显著低于相同尺寸和类型的色数组中位数。",
                        )
                    )

    def _detect_color_inversions(self, records: list[NormalizedQuote]) -> None:
        grouped: dict[tuple[object, ...], list[NormalizedQuote]] = defaultdict(list)
        for record in records:
            if record.unit_cost is not None and record.colors_count is not None:
                key = (record.product_type, record.width_cm, record.height_cm, record.variant_type)
                grouped[key].append(record)
        for peers in grouped.values():
            ordered = sorted(peers, key=lambda record: record.colors_count or 0)
            for lower, higher in zip(ordered, ordered[1:], strict=False):
                assert lower.unit_cost is not None and higher.unit_cost is not None
                if higher.unit_cost < lower.unit_cost * self.color_inversion_ratio:
                    higher.add_issue(
                        _warning(
                            IssueCode.COLOR_COST_INVERSION,
                            "更多色数的报价显著低于同尺寸较少色数报价。",
                        )
                    )

    def _detect_size_inversions(self, records: list[NormalizedQuote]) -> None:
        grouped: dict[tuple[object, ...], list[NormalizedQuote]] = defaultdict(list)
        for record in records:
            if record.unit_cost is not None and record.width_cm and record.height_cm:
                grouped[(record.product_type, record.colors_count, record.variant_type)].append(
                    record
                )
        for peers in grouped.values():
            ordered = sorted(
                peers, key=lambda record: (record.width_cm or 0) * (record.height_cm or 0)
            )
            for smaller, larger in zip(ordered, ordered[1:], strict=False):
                assert smaller.unit_cost is not None and larger.unit_cost is not None
                if larger.unit_cost < smaller.unit_cost * self.size_inversion_ratio:
                    larger.add_issue(
                        _warning(
                            IssueCode.SIZE_COST_INVERSION,
                            "更大面积规格的报价显著低于相邻较小规格报价。",
                        )
                    )
