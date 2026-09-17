"""Add factory quote catalog import support.

Revision ID: 20260915_0002
Revises: 20260915_0001
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260915_0002"
down_revision: str | None = "20260915_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("currency", sa.String(length=3), server_default="CNY", nullable=False),
    )

    op.add_column("import_batches", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.add_column("import_batches", sa.Column("source_sheet", sa.String(length=255), nullable=True))
    op.add_column(
        "import_batches",
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_batches",
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_import_batches_supplier_id_suppliers"),
        "import_batches",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_import_batches_supplier_id"),
        "import_batches",
        ["supplier_id"],
        unique=False,
    )

    op.drop_constraint(
        "uq_factory_costs_supplier_variant_effective",
        "factory_costs",
        type_="unique",
    )
    op.add_column(
        "factory_costs",
        sa.Column(
            "product_type",
            sa.String(length=64),
            server_default="PAINT_BY_NUMBERS",
            nullable=False,
        ),
    )
    op.add_column("factory_costs", sa.Column("size_code", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE factory_costs SET size_code = "
        "regexp_replace(width_cm::text, '\\.?0+$', '') || 'x' || "
        "regexp_replace(height_cm::text, '\\.?0+$', '') "
        "WHERE size_code IS NULL"
    )
    op.alter_column("factory_costs", "size_code", nullable=False)
    op.add_column(
        "factory_costs",
        sa.Column("shipping_included", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "factory_costs",
        sa.Column(
            "cost_completeness_status",
            sa.Enum(
                "COMPLETE",
                "INCOMPLETE",
                "UNKNOWN",
                name="cost_completeness_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="INCOMPLETE",
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_factory_costs_cost_completeness_status"),
        "factory_costs",
        ["cost_completeness_status"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_factory_costs_supplier_variant_effective",
        "factory_costs",
        [
            "supplier_id",
            "product_type",
            "colors_count",
            "width_cm",
            "height_cm",
            "framed",
            "effective_from",
        ],
    )

    op.create_table(
        "factory_quote_rows",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_column", sa.String(length=16), nullable=False),
        sa.Column("product_type", sa.String(length=64), nullable=False),
        sa.Column("variant_type", sa.String(length=16), nullable=False),
        sa.Column("raw_color", sa.String(length=128), nullable=True),
        sa.Column("raw_size", sa.String(length=256), nullable=True),
        sa.Column("raw_cost", sa.String(length=128), nullable=True),
        sa.Column("colors_count", sa.Integer(), nullable=True),
        sa.Column("size_code", sa.String(length=32), nullable=True),
        sa.Column("width_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("shipping_included", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "row_status",
            sa.Enum(
                "VALID",
                "WARNING",
                "ERROR",
                "SKIPPED",
                name="factory_quote_row_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(width_cm IS NULL AND height_cm IS NULL) OR "
            "(width_cm IS NOT NULL AND height_cm IS NOT NULL)",
            name=op.f("ck_factory_quote_rows_dimension_pair"),
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name=op.f("ck_factory_quote_rows_unit_cost_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_factory_quote_rows_import_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_factory_quote_rows_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_factory_quote_rows")),
        sa.UniqueConstraint(
            "import_batch_id",
            "source_sheet",
            "source_row",
            "variant_type",
            name="uq_factory_quote_rows_batch_source_variant",
        ),
    )
    op.create_index(
        op.f("ix_factory_quote_rows_import_batch_id"),
        "factory_quote_rows",
        ["import_batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_factory_quote_rows_supplier_id"),
        "factory_quote_rows",
        ["supplier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_factory_quote_rows_row_status"),
        "factory_quote_rows",
        ["row_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_factory_quote_rows_row_status"), table_name="factory_quote_rows")
    op.drop_index(op.f("ix_factory_quote_rows_supplier_id"), table_name="factory_quote_rows")
    op.drop_index(op.f("ix_factory_quote_rows_import_batch_id"), table_name="factory_quote_rows")
    op.drop_table("factory_quote_rows")

    op.drop_constraint(
        "uq_factory_costs_supplier_variant_effective",
        "factory_costs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_factory_costs_supplier_variant_effective",
        "factory_costs",
        [
            "supplier_id",
            "colors_count",
            "width_cm",
            "height_cm",
            "framed",
            "effective_from",
        ],
    )
    op.drop_index(op.f("ix_factory_costs_cost_completeness_status"), table_name="factory_costs")
    op.drop_column("factory_costs", "cost_completeness_status")
    op.drop_column("factory_costs", "shipping_included")
    op.drop_column("factory_costs", "size_code")
    op.drop_column("factory_costs", "product_type")

    op.drop_index(op.f("ix_import_batches_supplier_id"), table_name="import_batches")
    op.drop_constraint(
        op.f("fk_import_batches_supplier_id_suppliers"),
        "import_batches",
        type_="foreignkey",
    )
    op.drop_column("import_batches", "skipped_count")
    op.drop_column("import_batches", "warning_count")
    op.drop_column("import_batches", "source_sheet")
    op.drop_column("import_batches", "supplier_id")

    op.drop_column("suppliers", "currency")
