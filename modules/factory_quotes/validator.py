from modules.factory_quotes.schemas import (
    IssueCode,
    NormalizedQuote,
    Severity,
    ValidationIssue,
)


class FactoryQuoteValidator:
    def __init__(self, allowed_color_counts: set[int]) -> None:
        self.allowed_color_counts = allowed_color_counts

    def validate(self, record: NormalizedQuote) -> NormalizedQuote:
        if any(issue.issue_code is IssueCode.SEPARATOR_ROW for issue in record.issues):
            return record

        if record.colors_count is None and not any(
            issue.issue_code is IssueCode.INVALID_COLOR_COUNT for issue in record.issues
        ):
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.MISSING_COLOR_COUNT,
                    message="缺少色数。",
                )
            )
        elif (
            record.colors_count is not None and record.colors_count not in self.allowed_color_counts
        ):
            record.add_issue(
                ValidationIssue(
                    severity=Severity.WARNING,
                    issue_code=IssueCode.UNKNOWN_COLOR_COUNT,
                    message=f"色数 {record.colors_count} 不在当前允许列表中，需要人工确认。",
                )
            )

        if record.width_cm is None or record.height_cm is None or record.size_code is None:
            if not any(issue.issue_code is IssueCode.INVALID_DIMENSION for issue in record.issues):
                record.add_issue(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        issue_code=IssueCode.INVALID_DIMENSION,
                        message=f"缺少或无法解析尺寸：{record.raw_size!r}。",
                    )
                )

        if record.unit_cost is None:
            if not any(issue.issue_code is IssueCode.INVALID_COST for issue in record.issues):
                record.add_issue(
                    ValidationIssue(
                        severity=Severity.INFO,
                        issue_code=IssueCode.NO_QUOTE,
                        message="该规格没有报价，已跳过正式成本写入。",
                    )
                )
        elif record.unit_cost < 0:
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.NEGATIVE_COST,
                    message="报价不能为负数。",
                )
            )
        elif record.unit_cost == 0:
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.ZERO_COST,
                    message="0 元报价不是有效商品成本。",
                )
            )
        return record
