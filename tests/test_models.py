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
    "stores",
    "integration_connections",
    "integration_sync_cursors",
    "integration_runs",
    "platform_events",
    "platform_assets",
    "listing_submissions",
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


def test_temu_listing_tracks_store_scoped_external_identifiers() -> None:
    table = Base.metadata.tables["temu_listings"]
    assert {
        "dianxiaomi_spu_id",
        "temu_spu",
        "temu_skc_id",
        "temu_sku_id",
        "platform_review_status",
        "platform_lifecycle_status",
        "external_id_source",
        "external_id_observed_at",
    } <= set(table.c.keys())
    constraints = {constraint.name for constraint in table.constraints if constraint.name}
    assert "uq_temu_listings_store_temu_sku_id" in constraints


def test_integration_tables_enforce_idempotency_and_no_plaintext_secret_column() -> None:
    connection_columns = set(Base.metadata.tables["integration_connections"].c.keys())
    assert "credential_reference" in connection_columns
    assert "access_token" not in connection_columns
    assert "app_secret" not in connection_columns

    run_key = Base.metadata.tables["integration_runs"].c.idempotency_key
    submission_key = Base.metadata.tables["listing_submissions"].c.idempotency_key
    assert run_key.unique is True
    assert submission_key.unique is True


def test_platform_events_are_deduplicated_per_connection() -> None:
    constraints = {
        constraint.name
        for constraint in Base.metadata.tables["platform_events"].constraints
        if constraint.name
    }
    assert "uq_platform_events_connection_external_event" in constraints
