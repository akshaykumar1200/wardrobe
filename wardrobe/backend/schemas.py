from datetime import datetime, date
from typing import Optional, List, Dict
import re
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10)
    display_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        return v.strip().lower()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: Optional[str]
    is_admin: bool
    created_at: Optional[datetime]


class UserUpdate(BaseModel):
    display_name: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def sensible_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not 1 <= len(v) <= 60:
            raise ValueError("display name must be 1 to 60 characters")
        return v


class ItemCandidate(BaseModel):
    name: str
    category: str
    stored_name: str
    color: Optional[str] = None
    bytes: int = 0
    image_url: str


CATEGORIES = ("topwear", "bottomwear", "shoes", "accessories", "other")


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str
    # Empty for a manually added garment, which has no photo at all.
    stored_name: str = ""
    color: Optional[str] = None
    upload_id: Optional[int] = None
    is_manual: int = 0

    @field_validator("category")
    @classmethod
    def known_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
        return v


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None

    @field_validator("category")
    @classmethod
    def known_category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
        return v
    color: Optional[str] = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    category: str
    stored_name: str
    color: Optional[str]
    bytes: int
    upload_id: Optional[int]
    is_manual: int
    created_at: datetime
    image_url: str


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_items: int
    total_uploads: int
    storage_bytes: int
    items_by_category: Dict[str, int]
    signups_last_7d: int


class OutfitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    item_ids: list[int]

    @field_validator("item_ids")
    @classmethod
    def valid_item_ids(cls, v: list[int]) -> list[int]:
        if not 1 <= len(v) <= 8:
            raise ValueError("item_ids must contain 1 to 8 items")
        if len(set(v)) != len(v):
            raise ValueError("item_ids must not contain duplicates")
        return v


class OutfitScoreRequest(BaseModel):
    item_ids: list[int]

    @field_validator("item_ids")
    @classmethod
    def valid_item_ids(cls, v: list[int]) -> list[int]:
        if not 1 <= len(v) <= 8:
            raise ValueError("item_ids must contain 1 to 8 items")
        if len(set(v)) != len(v):
            raise ValueError("item_ids must not contain duplicates")
        return v


class OutfitItemOut(BaseModel):
    item_id: int | None
    name: str
    available: bool
    image_url: str | None


class OutfitOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    items: list[OutfitItemOut]


class WearCreate(BaseModel):
    item_ids: list[int]
    worn_on: str | None = None
    outfit_id: int | None = None

    @field_validator("item_ids")
    @classmethod
    def valid_item_ids(cls, v: list[int]) -> list[int]:
        if not 1 <= len(v) <= 8:
            raise ValueError("item_ids must contain 1 to 8 items")
        if len(set(v)) != len(v):
            raise ValueError("item_ids must not contain duplicates")
        return v

    @field_validator("worn_on")
    @classmethod
    def valid_worn_on(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("worn_on must be a valid YYYY-MM-DD date")
        try:
            date.fromisoformat(v)
        except (TypeError, ValueError):
            raise ValueError("worn_on must be a valid YYYY-MM-DD date")
        return v


class WearOut(BaseModel):
    id: int
    worn_on: str
    outfit_id: int | None
    created_at: datetime
    items: list[OutfitItemOut]
    already_recorded: bool
