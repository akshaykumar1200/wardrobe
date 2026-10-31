from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session as DBSession

from backend.auth import current_user, limiter
from backend.database import get_db
from backend.models import Item, Outfit, OutfitItem, User
from backend.schemas import OutfitCreate, OutfitItemOut, OutfitOut, OutfitScoreRequest
from backend.outfit_color import rank_combinations, score_outfit
from backend.scoring import describe

router = APIRouter(prefix="/api/outfits", tags=["outfits"])


def _items_out(links: list[OutfitItem], db: DBSession) -> list[OutfitItemOut]:
    ids = [link.item_id for link in links if link.item_id is not None]
    live = {item.id: item for item in db.query(Item).filter(Item.id.in_(ids)).all()} if ids else {}
    result = []
    for link in links:
        item = live.get(link.item_id)
        result.append(OutfitItemOut(
            item_id=item.id if item else None,
            name=link.item_name,
            available=item is not None,
            # A manual garment has no file, so an empty stored_name must stay null
        # rather than become a URL that 404s and renders as a blank tile.
        image_url=f"/api/images/item/{item.stored_name}" if item and item.stored_name else None,
        ))
    return result


def _outfit_out(outfit: Outfit, db: DBSession) -> OutfitOut:
    return OutfitOut(id=outfit.id, name=outfit.name, created_at=outfit.created_at,
                     items=_items_out(outfit.items, db))


@router.post("", response_model=OutfitOut)
def create_outfit(payload: OutfitCreate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    items = db.query(Item).filter(Item.user_id == user.id, Item.id.in_(payload.item_ids)).all()
    if len(items) < len(payload.item_ids):
        raise HTTPException(400, "No such garment in your wardrobe")
    by_id = {item.id: item for item in items}
    outfit = Outfit(user_id=user.id, name=payload.name.strip())
    outfit.items = [OutfitItem(item_id=item_id, item_name=by_id[item_id].name) for item_id in payload.item_ids]
    db.add(outfit)
    db.commit()
    db.refresh(outfit)
    return _outfit_out(outfit, db)


@router.get("", response_model=list[OutfitOut])
def list_outfits(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    outfits = db.query(Outfit).filter(Outfit.user_id == user.id).order_by(Outfit.created_at.desc()).all()
    return [_outfit_out(outfit, db) for outfit in outfits]


@router.get("/recommendations")
# Scores every combination in the closet, so it is the costliest read we serve.
@limiter.limit("30/minute")
def outfit_recommendations(
    request: Request,
    limit: int = Query(default=5, ge=1, le=10),
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    rows = db.query(Item).filter(Item.user_id == user.id).order_by(Item.id.asc()).all()
    tops = [item for item in rows if item.category == "topwear"]
    bottoms = [item for item in rows if item.category == "bottomwear"]
    shoes = [item for item in rows if item.category == "shoes"]

    if not tops or not bottoms:
        return {"suggestions": [], "guidance": "Add at least one top and one bottom."}
    if len(tops) * len(bottoms) * max(len(shoes), 1) > 20000:
        raise HTTPException(400, "Too many combinations. Narrow your wardrobe first.")

    wardrobe = [description for item in rows if (description := describe(item)) is not None]
    ranked = rank_combinations(wardrobe, top_n=limit)
    ranked.sort(key=lambda result: (-result["score"], tuple(result["items"])))
    by_id = {item.id: item for item in rows}
    suggestions = []
    for result in ranked:
        suggestions.append({
            "items": [
                {
                    "id": (item := by_id[item_id]).id,
                    "name": item.name,
                    "category": item.category,
                    "image_url": f"/api/images/item/{item.stored_name}" if item.stored_name else None,
                }
                for item_id in result["items"]
            ],
            "score": result["score"],
            "verdict": result["verdict"],
            "notes": result["notes"],
            "palette": result["palette"],
        })
    return {"suggestions": suggestions}


@router.get("/{outfit_id}", response_model=OutfitOut)
def get_outfit(outfit_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id, Outfit.user_id == user.id).first()
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return _outfit_out(outfit, db)


@router.delete("/{outfit_id}")
def delete_outfit(outfit_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id, Outfit.user_id == user.id).first()
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    db.delete(outfit)
    db.commit()
    return {"deleted": outfit_id}


@router.post("/score")
def score_saved_items(payload: OutfitScoreRequest, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    rows = db.query(Item).filter(
        Item.user_id == user.id,
        Item.id.in_(payload.item_ids),
    ).all()
    if len(rows) < len(payload.item_ids):
        raise HTTPException(400, "No such garment in your wardrobe")

    descriptions = [description for item in rows if (description := describe(item)) is not None]
    if len(descriptions) < 2:
        raise HTTPException(400, "Need two scorable garments")
    result = score_outfit(descriptions)
    if result is None:
        raise HTTPException(400, "Need two scorable garments")
    return result


