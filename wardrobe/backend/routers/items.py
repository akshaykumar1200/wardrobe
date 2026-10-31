import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from PIL import Image, ImageOps
from sqlalchemy.orm import Session as DBSession
from starlette.concurrency import run_in_threadpool

from backend import crops, flatten, storage
from backend.config import settings
from backend.database import get_db
from backend.models import User, Item, Upload
from backend.schemas import ItemCreate, ItemUpdate, ItemOut
from backend.auth import current_user, limiter

router = APIRouter(prefix="/api/items", tags=["items"])


def _item_to_out(item: Item) -> ItemOut:
    return ItemOut(
        id=item.id,
        user_id=item.user_id,
        name=item.name,
        category=item.category,
        stored_name=item.stored_name,
        color=item.color,
        bytes=item.bytes,
        upload_id=item.upload_id,
        is_manual=item.is_manual,
        created_at=item.created_at,
        image_url=f"/api/images/item/{item.stored_name}"
    )


@router.post("", response_model=ItemOut)
def create_item(payload: ItemCreate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    # Size comes from the file on disk, never from the client. A caller could
    # otherwise claim any figure and skew the admin storage totals.
    size = 0
    if payload.stored_name:
        if not crops.exists(db, user.id, payload.stored_name):
            raise HTTPException(400, "No such image for this account")
        crop_data = crops.get(db, user.id, payload.stored_name)
        size = len(crop_data)

    item = Item(
        user_id=user.id,
        name=payload.name.strip(),
        category=payload.category,
        stored_name=payload.stored_name,
        color=payload.color,
        bytes=size,
        upload_id=payload.upload_id,
        is_manual=payload.is_manual
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.get("", response_model=List[ItemOut])
def list_items(
    category: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = "newest",
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db)
):
    query = db.query(Item).filter(Item.user_id == user.id)

    if category and category != "all":
        query = query.filter(Item.category == category)

    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))

    if sort == "oldest":
        query = query.order_by(Item.created_at.asc())
    else:
        query = query.order_by(Item.created_at.desc())

    items = query.all()
    return [_item_to_out(i) for i in items]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id, Item.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    return _item_to_out(item)


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(item_id: int, payload: ItemUpdate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id, Item.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    if payload.name is not None:
        item.name = payload.name
    if payload.category is not None:
        item.category = payload.category
    if payload.color is not None:
        item.color = payload.color

    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.delete("/{item_id}")
def delete_item(item_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id, Item.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    # Crop filenames are content hashes, so two items can legitimately point at
    # one file. Only the last reference may remove it.
    shared = db.query(Item).filter(
        Item.user_id == user.id,
        Item.stored_name == item.stored_name,
        Item.id != item.id,
    ).first()
    if shared is None:
        crops.delete(db, user.id, item.stored_name)
        crops.delete(db, user.id, "flat-" + item.stored_name)

    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.post("/{item_id}/flat")
@limiter.limit("6/minute")
async def flat_item(
    item_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == item_id, Item.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if item.category != "topwear":
        raise HTTPException(400, "Flat view works for tops only for now.")
    upload = db.query(Upload).filter(Upload.id == item.upload_id, Upload.user_id == user.id).first() if item.upload_id else None
    if not upload or settings.CLOUD_MODE:
        raise HTTPException(400, "The original photo for this item isn't stored on this server.")
    original = (storage.get_user_storage_dir(user.id, "originals") / upload.stored_name)
    if not original.is_file():
        raise HTTPException(400, "The original photo for this item isn't stored on this server.")
    try:
        with Image.open(original) as opened:
            photo = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception:
        raise HTTPException(400, "The original photo for this item isn't stored on this server.")
    try:
        png, info = await run_in_threadpool(flatten.flatten_top, photo)
    except flatten.NotSuitable as exc:
        raise HTTPException(422, str(exc))
    except flatten.ModelMissing:
        raise HTTPException(503, "Flat view isn't available on this server.")
    stored_name = "flat-" + item.stored_name
    crops.delete(db, user.id, stored_name)
    crops.put(db, user.id, stored_name, png)
    db.commit()
    return {"stored_name": stored_name, **info}
