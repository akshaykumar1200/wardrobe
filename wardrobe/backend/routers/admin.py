from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from backend.database import get_db
from backend.models import User, Item, Upload, Session
from backend.schemas import AdminStats
from backend.auth import current_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
def get_stats(admin: User = Depends(current_admin), db: DBSession = Depends(get_db)):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == 1).scalar() or 0
    total_items = db.query(func.count(Item.id)).scalar() or 0
    total_uploads = db.query(func.count(Upload.id)).scalar() or 0

    upload_bytes = db.query(func.sum(Upload.bytes)).scalar() or 0
    item_bytes = db.query(func.sum(Item.bytes)).scalar() or 0
    total_bytes = upload_bytes + item_bytes

    cat_rows = db.query(Item.category, func.count(Item.id)).group_by(Item.category).all()
    items_by_category = {cat: count for cat, count in cat_rows}

    signups_7d = db.query(func.count(User.id)).filter(User.created_at >= seven_days_ago).scalar() or 0

    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        total_items=total_items,
        total_uploads=total_uploads,
        storage_bytes=total_bytes,
        items_by_category=items_by_category,
        signups_last_7d=signups_7d
    )


@router.get("/users")
def get_users(admin: User = Depends(current_admin), db: DBSession = Depends(get_db)):
    users = db.query(User).all()
    result = []
    for u in users:
        item_count = db.query(func.count(Item.id)).filter(Item.user_id == u.id).scalar() or 0
        upload_count = db.query(func.count(Upload.id)).filter(Upload.user_id == u.id).scalar() or 0
        result.append({
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "is_admin": bool(u.is_admin),
            "is_active": bool(u.is_active),
            "item_count": item_count,
            "upload_count": upload_count,
            "created_at": u.created_at,
            "last_login": u.last_login
        })
    return result


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, admin: User = Depends(current_admin), db: DBSession = Depends(get_db)):
    """Return a generated password once; it is never readable again after this response."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(password)
    db.query(Session).filter(Session.user_id == user_id).delete()
    db.commit()
    return {"password": password}
