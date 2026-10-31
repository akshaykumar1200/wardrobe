from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, LargeBinary, func
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    is_admin = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    uploads = relationship("Upload", back_populates="user", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="user", cascade="all, delete-orphan")
    blobs = relationship("Blob", back_populates="user", cascade="all, delete-orphan")
    outfits = relationship("Outfit", back_populates="user", cascade="all, delete-orphan")
    wear_events = relationship("WearEvent", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    token = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)

    user = relationship("User", back_populates="sessions")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    token_hash = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="password_resets")


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stored_name = Column(String, nullable=False)
    bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="uploads")
    items = relationship("Item", back_populates="upload")


class Blob(Base):
    __tablename__ = "blobs"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stored_name = Column(String, primary_key=True)
    data = Column(LargeBinary, nullable=False)
    bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="blobs")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    stored_name = Column(String, nullable=False)
    color = Column(String, nullable=True)
    bytes = Column(Integer, default=0)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True)
    is_manual = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="items")
    upload = relationship("Upload", back_populates="items")


class Outfit(Base):
    __tablename__ = "outfits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="outfits")
    items = relationship("OutfitItem", back_populates="outfit", cascade="all, delete-orphan")


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    outfit_id = Column(Integer, ForeignKey("outfits.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    # shortcut: name snapshot, not a full item copy; history shows "unavailable" for deleted items
    item_name = Column(String, nullable=False)

    outfit = relationship("Outfit", back_populates="items")


class WearEvent(Base):
    __tablename__ = "wear_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    worn_on = Column(String, nullable=False)
    composition_key = Column(String, nullable=False)
    outfit_id = Column(Integer, ForeignKey("outfits.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="wear_events")
    outfit = relationship("Outfit")
    items = relationship("WearEventItem", back_populates="wear_event", cascade="all, delete-orphan")


class WearEventItem(Base):
    __tablename__ = "wear_event_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wear_event_id = Column(Integer, ForeignKey("wear_events.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    # shortcut: name snapshot, not a full item copy; history shows "unavailable" for deleted items
    item_name = Column(String, nullable=False)

    wear_event = relationship("WearEvent", back_populates="items")


Index("idx_outfits_user", Outfit.user_id)
Index("idx_wears_user", WearEvent.user_id)
Index("uq_wears_user_day_composition", WearEvent.user_id, WearEvent.worn_on, WearEvent.composition_key, unique=True)


Index("idx_items_user", Item.user_id)
Index("idx_items_user_cat", Item.user_id, Item.category)
Index("idx_sessions_user", Session.user_id)
Index("idx_uploads_user", Upload.user_id)
Index("idx_blobs_user", Blob.user_id)
