import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
POSTGRES_URL = os.getenv("POSTGRES_URL")
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL environment variable not set")

# SQLAlchemy 2.0 style async engine
_engine: Optional[AsyncEngine] = None


def get_async_engine() -> AsyncEngine:
    """Create (or reuse) a single async engine instance.

    The engine URL should be of the form:
    ``postgresql+asyncpg://user:password@host:port/dbname``
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(POSTGRES_URL, echo=False, future=True)
    return _engine


AsyncSessionLocal = async_sessionmaker(get_async_engine(), expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Core tables (leaned down to the essentials required for the AI endpoints)
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    role: Mapped[str] = mapped_column(String, nullable=False)  # customer, staff, admin
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(back_populates="user")

    def __repr__(self) -> str:  # pragma: no cover
        return f"User(id={self.id}, role={self.role})"


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    ai_model_version: Mapped[str] = mapped_column(String, nullable=False, server_default="v1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(back_populates="restaurant")
    tables: Mapped[list["Table"]] = relationship(back_populates="restaurant")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Restaurant(id={self.id}, name={self.name})"


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "user_id", name="uq_waitlist_restaurant_user"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    restaurant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_position: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_wait_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_wait_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    restaurant: Mapped[Restaurant] = relationship(back_populates="waitlist_entries")
    user: Mapped[User] = relationship(back_populates="waitlist_entries")
    prediction: Mapped[Optional["PredictedWaitTime"]] = relationship(back_populates="waitlist_entry", uselist=False)
    seating_record: Mapped[Optional["SeatingRecord"]] = relationship(back_populates="waitlist_entry", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"WaitlistEntry(id={self.id}, position={self.queue_position})"


class PredictedWaitTime(Base):
    __tablename__ = "predicted_wait_times"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    restaurant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    waitlist_entry_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("waitlist_entries.id"), nullable=False)
    predicted_wait: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_factors: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    restaurant: Mapped[Restaurant] = relationship()
    waitlist_entry: Mapped[WaitlistEntry] = relationship(back_populates="prediction")

    def __repr__(self) -> str:  # pragma: no cover
        return f"PredictedWaitTime(id={self.id}, minutes={self.predicted_wait})"


class Table(Base):
    __tablename__ = "tables"
    __table_args__ = (UniqueConstraint("restaurant_id", "table_number", name="uq_table_number_restaurant"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    restaurant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    table_number: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("available", "occupied", "reserved", name="table_status_enum"), nullable=False, server_default="available"
    )
    last_cleaned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    restaurant: Mapped[Restaurant] = relationship(back_populates="tables")
    seating_records: Mapped[list["SeatingRecord"]] = relationship(back_populates="table")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Table(id={self.id}, number={self.table_number}, status={self.status})"


class SeatingRecord(Base):
    __tablename__ = "seating_records"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    waitlist_entry_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("waitlist_entries.id"), nullable=False)
    table_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tables.id"), nullable=False)
    seated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfaction_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    waitlist_entry: Mapped[WaitlistEntry] = relationship(back_populates="seating_record")
    table: Mapped[Table] = relationship(back_populates="seating_records")

    def __repr__(self) -> str:  # pragma: no cover
        return f"SeatingRecord(id={self.id}, table_id={self.table_id})"

# ---------------------------------------------------------------------------
# Dependency helper used by route handlers
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
