from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from backend.auth import current_user
from backend.database import get_db
from backend.models import Item, User, WearEvent, WearEventItem, Outfit
from backend.schemas import OutfitItemOut, WearCreate, WearOut

router = APIRouter(prefix="/api/wears", tags=["wears"])


def _items_out(links: list[WearEventItem], db: DBSession) -> list[OutfitItemOut]:
    ids = [link.item_id for link in links if link.item_id is not None]
    live = {item.id: item for item in db.query(Item).filter(Item.id.in_(ids)).all()} if ids else {}
    return [OutfitItemOut(
        item_id=(item.id if (item := live.get(link.item_id)) else None),
        name=link.item_name,
        available=item is not None,
        # A manual garment has no file, so an empty stored_name must stay null
        # rather than become a URL that 404s and renders as a blank tile.
        image_url=f"/api/images/item/{item.stored_name}" if item and item.stored_name else None,
    ) for link in links]


def _wear_out(event: WearEvent, db: DBSession, already_recorded: bool = False) -> WearOut:
    return WearOut(id=event.id, worn_on=event.worn_on, outfit_id=event.outfit_id,
                   created_at=event.created_at, items=_items_out(event.items, db),
                   already_recorded=already_recorded)


@router.post("", response_model=WearOut)
def create_wear(payload: WearCreate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    items = db.query(Item).filter(Item.user_id == user.id, Item.id.in_(payload.item_ids)).all()
    if len(items) < len(payload.item_ids):
        raise HTTPException(400, "No such garment in your wardrobe")
    if payload.outfit_id is not None:
        owned_outfit = db.query(Outfit).filter(Outfit.id == payload.outfit_id, Outfit.user_id == user.id).first()
        if not owned_outfit:
            raise HTTPException(404, "Outfit not found")

    worn_on = payload.worn_on or date.today().isoformat()
    composition_key = ",".join(str(item_id) for item_id in sorted(payload.item_ids))
    event = db.query(WearEvent).filter(
        WearEvent.user_id == user.id,
        WearEvent.worn_on == worn_on,
        WearEvent.composition_key == composition_key,
    ).first()
    if event:
        return _wear_out(event, db, True)

    by_id = {item.id: item for item in items}
    event = WearEvent(user_id=user.id, worn_on=worn_on, composition_key=composition_key,
                      outfit_id=payload.outfit_id)
    event.items = [WearEventItem(item_id=item_id, item_name=by_id[item_id].name)
                   for item_id in payload.item_ids]
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # Two taps arriving together both miss the check above. The unique index
        # keeps one row; return that instead of a 500, so a retry never counts twice.
        db.rollback()
        kept = db.query(WearEvent).filter(
            WearEvent.user_id == user.id,
            WearEvent.worn_on == worn_on,
            WearEvent.composition_key == composition_key,
        ).first()
        if not kept:
            raise
        return _wear_out(kept, db, True)
    db.refresh(event)
    return _wear_out(event, db, False)


@router.get("/stats")
def wear_stats(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    rows = db.query(
        WearEventItem.item_id,
        func.count(WearEventItem.id),
        func.max(WearEvent.worn_on),
    ).join(WearEvent, WearEvent.id == WearEventItem.wear_event_id).filter(
        WearEvent.user_id == user.id,
        WearEventItem.item_id.isnot(None),
    ).group_by(WearEventItem.item_id).all()
    return {
        "counts": {str(item_id): count for item_id, count, _last in rows},
        "last_worn": {str(item_id): last for item_id, _count, last in rows},
    }


@router.get("", response_model=list[WearOut])
def list_wears(limit: int = Query(50, le=200), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    events = db.query(WearEvent).filter(WearEvent.user_id == user.id).order_by(
        WearEvent.worn_on.desc(), WearEvent.created_at.desc()).limit(limit).all()
    return [_wear_out(event, db) for event in events]


@router.delete("/{wear_event_id}")
def delete_wear(wear_event_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    event = db.query(WearEvent).filter(WearEvent.id == wear_event_id, WearEvent.user_id == user.id).first()
    if not event:
        raise HTTPException(404, "Wear event not found")
    db.delete(event)
    db.commit()
    return {"deleted": wear_event_id}
