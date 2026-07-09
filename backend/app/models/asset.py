from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("user_id", "path", name="uq_assets_user_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    folder_id: Mapped[str | None] = mapped_column(
        ForeignKey("folders.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    stem: Mapped[str] = mapped_column(String(255), index=True)
    extension: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="assets")
    folder = relationship("Folder", back_populates="assets")
    tags = relationship("AssetTag", back_populates="asset", cascade="all, delete-orphan")

    @property
    def thumbnail_url(self) -> str | None:
        if not self.thumbnail_path:
            return None
        path = Path(self.thumbnail_path)
        parts = path.parts
        if "thumbnails" in parts:
            index = parts.index("thumbnails")
            return "/thumbnails/" + "/".join(parts[index + 1 :])
        return f"/thumbnails/{path.name}"
