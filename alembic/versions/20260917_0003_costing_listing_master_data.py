"""Add costing, fulfillment, and listing master data.

Revision ID: 20260917_0003
Revises: 20260915_0002
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260917_0003"
down_revision: str | None = "20260915_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("designs", sa.Column("factory_design_code", sa.String(64), nullable=True))
    op.add_column(
        "designs",
        sa.Column(
            "additional_image_paths",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column("designs", sa.Column("line_art_cost", sa.Numeric(14, 2), nullable=True))
    op.add_column("designs", sa.Column("line_art_cost_currency", sa.String(3), nullable=True))
    op.add_column(
        "designs",
        sa.Column("line_art_cost_paid", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("designs", sa.Column("line_art_cost_paid_at", sa.DateTime(timezone=True)))
    op.add_column(
        "designs",
        sa.Column("line_art_reusable", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index(
        op.f("ix_designs_factory_design_code"),
        "designs",
        ["factory_design_code"],
        unique=True,
    )
    op.create_unique_constraint("uq_products_design_id", "products", ["design_id"])

    op.add_column("skus", sa.Column("resolved_factory_cost_id", sa.Uuid(), nullable=True))
    op.add_column("skus", sa.Column("shipping_cost_usd", sa.Numeric(14, 2), nullable=True))
    op.add_column("skus", sa.Column("shipping_cost_type", sa.String(32), nullable=True))
    op.add_column("skus", sa.Column("exchange_rate", sa.Numeric(18, 8), nullable=True))
    op.add_column("skus", sa.Column("exchange_rate_source", sa.String(32), nullable=True))
    op.add_column(
        "skus", sa.Column("exchange_rate_timestamp", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("skus", sa.Column("unit_variable_cost_cny", sa.Numeric(14, 2)))
    op.add_column("skus", sa.Column("label_service_cost_cny", sa.Numeric(14, 2)))
    op.add_column("skus", sa.Column("label_service_cost_status", sa.String(32)))
    op.create_index(
        op.f("ix_skus_resolved_factory_cost_id"),
        "skus",
        ["resolved_factory_cost_id"],
        unique=False,
    )

    op.create_table(
        "packaging_rules",
        sa.Column("variant_type", sa.String(16), nullable=False),
        sa.Column("colors_count_condition", sa.String(32), nullable=False),
        sa.Column("width_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("height_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("box_length_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("box_width_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("box_height_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("max_units_per_box", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("source_hash", sa.String(64)),
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
            "width_cm > 0 AND height_cm > 0",
            name=op.f("ck_packaging_rules_product_dimensions_positive"),
        ),
        sa.CheckConstraint(
            "box_length_cm > 0 AND box_width_cm > 0 AND box_height_cm > 0",
            name=op.f("ck_packaging_rules_box_dimensions_positive"),
        ),
        sa.CheckConstraint(
            "max_units_per_box > 0", name=op.f("ck_packaging_rules_max_units_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_packaging_rules")),
        sa.UniqueConstraint(
            "variant_type",
            "colors_count_condition",
            "width_cm",
            "height_cm",
            "box_length_cm",
            "box_width_cm",
            "box_height_cm",
            name="uq_packaging_rules_variant_condition_size_box",
        ),
    )
    op.create_index(op.f("ix_packaging_rules_variant_type"), "packaging_rules", ["variant_type"])

    op.create_table(
        "product_weight_rules",
        sa.Column("width_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("height_cm", sa.Numeric(8, 2), nullable=False),
        sa.Column("colors_count", sa.Integer(), nullable=False),
        sa.Column("variant_type", sa.String(16), nullable=False),
        sa.Column("weight", sa.Numeric(12, 3), nullable=False),
        sa.Column("weight_unit", sa.String(8), server_default="g", nullable=False),
        sa.Column("package_description", sa.String(255)),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("source_hash", sa.String(64)),
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
            "width_cm > 0 AND height_cm > 0",
            name=op.f("ck_product_weight_rules_product_dimensions_positive"),
        ),
        sa.CheckConstraint(
            "colors_count > 0", name=op.f("ck_product_weight_rules_colors_count_positive")
        ),
        sa.CheckConstraint("weight > 0", name=op.f("ck_product_weight_rules_weight_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_weight_rules")),
        sa.UniqueConstraint(
            "width_cm",
            "height_cm",
            "colors_count",
            "variant_type",
            name="uq_product_weight_rules_variant",
        ),
    )
    op.create_index(
        op.f("ix_product_weight_rules_colors_count"),
        "product_weight_rules",
        ["colors_count"],
    )
    op.create_index(
        op.f("ix_product_weight_rules_variant_type"),
        "product_weight_rules",
        ["variant_type"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_weight_rules_variant_type"), table_name="product_weight_rules")
    op.drop_index(op.f("ix_product_weight_rules_colors_count"), table_name="product_weight_rules")
    op.drop_table("product_weight_rules")
    op.drop_index(op.f("ix_packaging_rules_variant_type"), table_name="packaging_rules")
    op.drop_table("packaging_rules")
    op.drop_index(op.f("ix_skus_resolved_factory_cost_id"), table_name="skus")
    for column in (
        "label_service_cost_status",
        "label_service_cost_cny",
        "unit_variable_cost_cny",
        "exchange_rate_timestamp",
        "exchange_rate_source",
        "exchange_rate",
        "shipping_cost_type",
        "shipping_cost_usd",
        "resolved_factory_cost_id",
    ):
        op.drop_column("skus", column)
    op.drop_constraint("uq_products_design_id", "products", type_="unique")
    op.drop_index(op.f("ix_designs_factory_design_code"), table_name="designs")
    for column in (
        "line_art_reusable",
        "line_art_cost_paid_at",
        "line_art_cost_paid",
        "line_art_cost_currency",
        "line_art_cost",
        "additional_image_paths",
        "factory_design_code",
    ):
        op.drop_column("designs", column)
