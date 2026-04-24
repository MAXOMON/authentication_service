from datetime import datetime
from typing import List, Optional

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, MetaData, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


metadata_obj = MetaData()


class Base(DeclarativeBase):
    __abstract__ = True

    metadata = metadata_obj

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"


class RefreshToken(Base):
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    device_id: Mapped[str] = mapped_column(Text, nullable=False)


class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
        server_onupdate=text("TIMEZONE('utc', now())"),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, default=None)
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", cascade="all, delete, delete-orphan", back_populates="user"
    )
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
