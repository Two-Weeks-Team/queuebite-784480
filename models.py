import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
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
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", ""))
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL or DATABASE_URL environment variable not set")

if POSTGRES_URL.startswith("postgresql+asyncpg://"):
    POSTGRES_URL = POSTGRES_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg://", 1
    )
elif POSTGRES_URL.startswith("postgres://"):
    POSTGRES_URL = POSTGRES_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif POSTGRES_URL.startswith("postgresql://") and "+psycopg" not in POSTGRES_URL:
    POSTGRES_URL = POSTGRES_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# asyncpg uses ?ssl=require but psycopg uses ?sslmode=require
if "?ssl=" in POSTGRES_URL and "sslmode" not in POSTGRES_URL:
    POSTGRES_URL = POSTGRES_URL.replace("?ssl=", "?sslmode=")
if "&ssl=" in POSTGRES_URL and "sslmode" not in POSTGRES_URL:
    POSTGRES_URL = POSTGRES_URL.replace("&ssl=", "&sslmode=")

connect_args: dict = {}
if (
    "localhost" not in POSTGRES_URL
    and "sslmode" not in POSTGRES_URL
    and "ssl" not in POSTGRES_URL
):
    connect_args["sslmode"] = "require"

engine = create_engine(POSTGRES_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="user"
    )


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    ai_model_version: Mapped[str] = mapped_column(
        String, nullable=False, server_default="v1.0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="restaurant"
    )
    tables: Mapped[list["Table"]] = relationship(back_populates="restaurant")


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id", "user_id", name="uq_waitlist_restaurant_user"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    restaurant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_position: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_wait_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    actual_wait_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="waitlist_entries")
    user: Mapped[User] = relationship(back_populates="waitlist_entries")
    prediction: Mapped[Optional["PredictedWaitTime"]] = relationship(
        back_populates="waitlist_entry", uselist=False
    )
    seating_record: Mapped[Optional["SeatingRecord"]] = relationship(
        back_populates="waitlist_entry", uselist=False
    )


class PredictedWaitTime(Base):
    __tablename__ = "predicted_wait_times"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    restaurant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False
    )
    waitlist_entry_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("waitlist_entries.id"), nullable=False
    )
    predicted_wait: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_factors: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    restaurant: Mapped[Restaurant] = relationship()
    waitlist_entry: Mapped[WaitlistEntry] = relationship(back_populates="prediction")


class Table(Base):
    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id", "table_number", name="uq_table_number_restaurant"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    restaurant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False
    )
    table_number: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("available", "occupied", "reserved", name="table_status_enum"),
        nullable=False,
        server_default="available",
    )
    last_cleaned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="tables")
    seating_records: Mapped[list["SeatingRecord"]] = relationship(
        back_populates="table"
    )


class SeatingRecord(Base):
    __tablename__ = "seating_records"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    waitlist_entry_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("waitlist_entries.id"), nullable=False
    )
    table_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tables.id"), nullable=False
    )
    seated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    satisfaction_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    waitlist_entry: Mapped[WaitlistEntry] = relationship(
        back_populates="seating_record"
    )
    table: Mapped[Table] = relationship(back_populates="seating_records")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
