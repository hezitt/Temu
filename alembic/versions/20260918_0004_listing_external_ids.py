"""Add store-scoped listing identifiers observed through Dianxiaomi.

Revision ID: 20260918_0004
Revises: 20260917_0003
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0004"
down_revision: str | None = "20260917_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("temu_listings", sa.Column("dianxiaomi_spu_id", sa.String(128)))
    op.add_column("temu_listings", sa.Column("temu_skc_id", sa.String(128)))
    op.add_column("temu_listings", sa.Column("temu_sku_id", sa.String(128)))
    op.add_column("temu_listings", sa.Column("platform_review_status", sa.String(32)))
    op.add_column("temu_listings", sa.Column("platform_lifecycle_status", sa.String(64)))
    op.add_column("temu_listings", sa.Column("external_id_source", sa.String(32)))
    op.add_column(
        "temu_listings", sa.Column("external_id_observed_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        op.f("ix_temu_listings_dianxiaomi_spu_id"),
        "temu_listings",
        ["dianxiaomi_spu_id"],
    )
    op.create_index(
        op.f("ix_temu_listings_temu_skc_id"), "temu_listings", ["temu_skc_id"]
    )
    op.create_index(
        op.f("ix_temu_listings_temu_sku_id"), "temu_listings", ["temu_sku_id"]
    )
    op.create_index(
        op.f("ix_temu_listings_platform_review_status"),
        "temu_listings",
        ["platform_review_status"],
    )
    op.create_unique_constraint(
        "uq_temu_listings_store_temu_sku_id",
        "temu_listings",
        ["store_code", "temu_sku_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_temu_listings_store_temu_sku_id", "temu_listings", type_="unique"
    )
    op.drop_index(
        op.f("ix_temu_listings_platform_review_status"), table_name="temu_listings"
    )
    op.drop_index(op.f("ix_temu_listings_temu_sku_id"), table_name="temu_listings")
    op.drop_index(op.f("ix_temu_listings_temu_skc_id"), table_name="temu_listings")
    op.drop_index(op.f("ix_temu_listings_dianxiaomi_spu_id"), table_name="temu_listings")
    for column in (
        "external_id_observed_at",
        "external_id_source",
        "platform_lifecycle_status",
        "platform_review_status",
        "temu_sku_id",
        "temu_skc_id",
        "dianxiaomi_spu_id",
    ):
        op.drop_column("temu_listings", column)
