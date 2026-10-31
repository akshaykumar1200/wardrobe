from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.database import get_db
from backend import crops
from sqlalchemy.orm import Session as DBSession
from backend.models import User
from backend.auth import current_user

router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("/item/{stored_name}")
def get_item_image(
    stored_name: str,
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    # Ownership is the directory, not an Item row. Requiring a row meant a freshly
    # segmented crop 404'd on the Review screen, because its item is only created
    # when the user taps Save -- so they approved cut-outs they could not see.
    # The path below is built from the signed-in user's own id, so one account can
    # never reach another's files.
    data = crops.get(db, user.id, stored_name)
    if data is None:
        raise HTTPException(404, "Not found")

    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"}
    )
