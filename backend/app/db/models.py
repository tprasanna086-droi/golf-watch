"""SQLAlchemy ORM models for glof-watch PostGIS tables."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Lake(Base):
    __tablename__ = "lakes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    district: Mapped[Optional[str]] = mapped_column(Text)
    basin: Mapped[Optional[str]] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    geom: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
    )
    initial_area_km2: Mapped[Optional[float]] = mapped_column()
    risk_class: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Lake id={self.id!r} name={self.name!r}>"


class LakeObservation(Base):
    __tablename__ = "lake_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lake_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("lakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    area_km2: Mapped[Optional[float]] = mapped_column()
    ndwi_mean: Mapped[Optional[float]] = mapped_column()
    turbidity_index: Mapped[Optional[float]] = mapped_column()
    shape_irregularity: Mapped[Optional[float]] = mapped_column()
    mask_geom: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326),
    )
    cloud_cover_pct: Mapped[Optional[float]] = mapped_column()
    sentinel_tile_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<LakeObservation lake_id={self.lake_id!r} "
            f"observed_at={self.observed_at!r}>"
        )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lake_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("lakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    alert_type: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[Optional[str]] = mapped_column(Text)
    area_delta_km2: Mapped[Optional[float]] = mapped_column()
    anomaly_score: Mapped[Optional[float]] = mapped_column()
    message: Mapped[Optional[str]] = mapped_column(Text)
    sms_sent: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<Alert id={self.id!r} lake_id={self.lake_id!r} "
            f"alert_type={self.alert_type!r} severity={self.severity!r}>"
        )
