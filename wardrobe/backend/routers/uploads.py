from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from starlette.concurrency import run_in_threadpool

from backend.database import get_db
from backend.models import User, Upload, Item
from backend.auth import current_user, limiter
from backend.storage import (
    validate_and_store_original,
    sweep_orphan_crops,
    use_crop_db,
)
from backend.segmenter import extract_garments

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("")
# The only endpoint that costs ~40s of CPU per call, and the only one that was
# unlimited.
@limiter.limit("5/minute")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db)
):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload file")

    content_type = file.content_type or "image/jpeg"

    # Validate, strip EXIF, and store original
    stored_name, file_bytes, img_clean = validate_and_store_original(
        raw, content_type, user.id
    )

    upload_record = (
        db.query(Upload)
        .filter(Upload.user_id == user.id, Upload.stored_name == stored_name)
        .first()
    )
    # The row is the duplicate test, not the originals folder: that folder is
    # gone after a Space restart and would call every old photo new again.
    is_duplicate = upload_record is not None

    if upload_record is None:
        upload_record = Upload(user_id=user.id, stored_name=stored_name, bytes=file_bytes)
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

    # Same photo already segmented: hand back what we produced last time rather
    # than paying for inference again and writing a second copy of every crop.
    if is_duplicate:
        existing = db.query(Item).filter(
            Item.user_id == user.id, Item.upload_id == upload_record.id
        ).all()
        if existing:
            return {
                "upload_id": upload_record.id,
                "original_stored_name": stored_name,
                "duplicate_of_existing": True,
                "notice": None,
                "candidates": [
                    {
                        "name": i.name,
                        "category": i.category,
                        "stored_name": i.stored_name,
                        "color": i.color,
                        "bytes": i.bytes,
                        "image_url": f"/api/images/item/{i.stored_name}",
                    }
                    for i in existing
                ],
            }

    # Reviews abandoned before saving left their crops behind; clear them while
    # we are already about to write new ones.
    keep = {
        name
        for (name,) in db.query(Item.stored_name).filter(Item.user_id == user.id).all()
    }
    await run_in_threadpool(sweep_orphan_crops, user.id, keep, db)

    # Run ML segmentation in threadpool so FastAPI event loop is not blocked
    with use_crop_db(db):
        result = await run_in_threadpool(extract_garments, img_clean, user.id)
    db.commit()

    return {
        "upload_id": upload_record.id,
        "original_stored_name": stored_name,
        # True whenever the photo itself was already stored, even though we had
        # to segment again because its items were never saved from Review.
        "duplicate_of_existing": is_duplicate,
        "notice": result["notice"],
        "candidates": result["items"]
    }
