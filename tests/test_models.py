from models import Base

REQUIRED_TABLES = {
    "designs",
    "products",
    "skus",
    "factory_costs",
    "temu_listings",
    "pricing_quotes",
    "pricing_decisions",
    "stock_orders",
    "stock_order_items",
    "labels",
    "shipments",
    "financial_transactions",
    "audit_logs",
    "packaging_rules",
    "product_weight_rules",
}


def test_required_tables_exist() -> None:
    assert REQUIRED_TABLES <= set(Base.metadata.tables)


def test_design_sku_trace_constraints_exist() -> None:
    sku_foreign_keys = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables["skus"].foreign_key_constraints
    }
    label_foreign_keys = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables["labels"].foreign_key_constraints
    }

    assert ("products.id", "products.design_id") in sku_foreign_keys
    assert ("skus.id", "skus.design_id") in label_foreign_keys


def test_finance_idempotency_key_is_unique() -> None:
    column = Base.metadata.tables["financial_transactions"].c.idempotency_key
    assert column.unique is True


def test_product_has_one_to_one_design_constraint() -> None:
    constraints = {
        constraint.name
        for constraint in Base.metadata.tables["products"].constraints
        if constraint.name
    }
    assert "uq_products_design_id" in constraints
