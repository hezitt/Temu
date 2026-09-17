from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PackagingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "packaging_rules"
    __table_args__ = (
        UniqueConstraint(
            "variant_type",
            "colors_count_condition",
            "width_cm",
            "height_cm",
            "box_length_cm",
            "box_width_cm",
            "box_height_cm",
            name="uq_packaging_rules_variant_condition_size_box",
        ),
        CheckConstraint("width_cm > 0 AND height_cm > 0", name="product_dimensions_positive"),
        CheckConstraint(
            "box_length_cm > 0 AND box_width_cm > 0 AND box_height_cm > 0",
            name="box_dimensions_positive",
        ),
        CheckConstraint("max_units_per_box > 0", name="max_units_positive"),
    )

    variant_type: Mapped[str] = mapped_column(String(16), index=True)
    colors_count_condition: Mapped[str] = mapped_column(String(32))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    box_length_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    box_width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    box_height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    max_units_per_box: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(512))
    source_hash: Mapped[str | None] = mapped_column(String(64))


class ProductWeightRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_weight_rules"
    __table_args__ = (
        UniqueConstraint(
            "width_cm",
            "height_cm",
            "colors_count",
            "variant_type",
            name="uq_product_weight_rules_variant",
        ),
        CheckConstraint("width_cm > 0 AND height_cm > 0", name="product_dimensions_positive"),
        CheckConstraint("colors_count > 0", name="colors_count_positive"),
        CheckConstraint("weight > 0", name="weight_positive"),
    )

    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    colors_count: Mapped[int] = mapped_column(Integer, index=True)
    variant_type: Mapped[str] = mapped_column(String(16), index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    weight_unit: Mapped[str] = mapped_column(String(8), default="g", server_default="g")
    package_description: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(512))
    source_hash: Mapped[str | None] = mapped_column(String(64))
