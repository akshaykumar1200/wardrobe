"""
main.py for f6 AI Fashion Wardrobe & Outfit Recommendation Engine
"""

import hashlib
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend import db
from backend.segmenter import extract_garments_from_bytes
from backend.outfit_color import rank_combinations, score_outfit

app = FastAPI(title="AURA Fashion AI Studio", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


# ---------------------------------------------------------------------------
# Extraction Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/extract")
async def extract_garments_api(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Uploaded file is empty.")

    if len(raw) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit.")

    sha = hashlib.sha256(raw).hexdigest()
    orig_filename = f"{sha[:32]}.jpg"
    orig_path = settings.ORIGINALS_DIR / orig_filename
    orig_path.write_bytes(raw)

    try:
        extraction_res = extract_garments_from_bytes(raw)
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {str(e)}")

    garments = extraction_res["garments"]
    if not garments:
        return {
            "success": False,
            "message": "No garments could be detected in this photo. Try a clearer shot with full garments visible.",
            "is_worn": extraction_res["is_worn"],
            "garments": []
        }

    return {
        "success": True,
        "is_worn": extraction_res["is_worn"],
        "person_confidence": extraction_res["person_confidence"],
        "garments": garments
    }


# ---------------------------------------------------------------------------
# Wardrobe Item CRUD Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/items")
def create_item(payload: dict = Body(...)):
    conn = db.get_conn()
    colors_json = json.dumps(payload.get("colors", []))
    cur = conn.execute(
        """
        INSERT INTO items (name, category, image_path, color_hex, color_name, colors_json, pattern, pattern_scale, area, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("name", "Untitled Piece"),
            payload.get("category", "other"),
            payload["image_path"],
            payload.get("color_hex", "#808080"),
            payload.get("color_name", "grey"),
            colors_json,
            payload.get("pattern", "solid"),
            payload.get("pattern_scale", "none"),
            payload.get("area", 0),
            payload.get("confidence", 1.0)
        )
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return {"success": True, "id": item_id}


@app.get("/api/items")
def list_items(category: str | None = None):
    conn = db.get_conn()
    if category and category != "all":
        rows = conn.execute("SELECT * FROM items WHERE category = ? ORDER BY id DESC", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        if d.get("colors_json"):
            try:
                d["colors"] = json.loads(d["colors_json"])
            except Exception:
                d["colors"] = []
        else:
            d["colors"] = [{"hex": d["color_hex"], "name": d["color_name"], "share": 1.0}]
        items.append(d)
    return items


@app.put("/api/items/{item_id}")
def update_item(item_id: int, payload: dict = Body(...)):
    conn = db.get_conn()
    conn.execute(
        """
        UPDATE items 
        SET name = ?, category = ?, color_hex = ?, color_name = ?, pattern = ?, pattern_scale = ?
        WHERE id = ?
        """,
        (
            payload.get("name"),
            payload.get("category"),
            payload.get("color_hex"),
            payload.get("color_name"),
            payload.get("pattern"),
            payload.get("pattern_scale"),
            item_id
        )
    )
    conn.commit()
    conn.close()
    return {"success": True, "updated_id": item_id}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    conn = db.get_conn()
    row = conn.execute("SELECT image_path FROM items WHERE id = ?", (item_id,)).fetchone()
    if row and row["image_path"]:
        file_path = Path("." + row["image_path"])
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"success": True, "deleted_id": item_id}


# ---------------------------------------------------------------------------
# Outfit Recommendation Engine
# ---------------------------------------------------------------------------

@app.get("/api/suggest")
def get_outfit_suggestions():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM items").fetchall()
    conn.close()

    wardrobe = []
    for r in rows:
        d = dict(r)
        if d.get("colors_json"):
            try:
                d["colors"] = json.loads(d["colors_json"])
            except Exception:
                d["colors"] = [{"hex": d["color_hex"], "name": d["color_name"], "share": 1.0}]
        else:
            d["colors"] = [{"hex": d["color_hex"], "name": d["color_name"], "share": 1.0}]
        wardrobe.append(d)

    if not wardrobe:
        return {"suggestions": [], "message": "Wardrobe is empty. Upload garments to get outfit suggestions."}

    ranked = rank_combinations(wardrobe, top_n=10)
    return {"suggestions": ranked}


@app.post("/api/wear")
def mark_outfit_worn(payload: dict = Body(...)):
    item_ids = payload.get("item_ids", [])
    if not item_ids:
        raise HTTPException(400, "item_ids list required")

    conn = db.get_conn()
    for i in item_ids:
        conn.execute("UPDATE items SET wear_count = wear_count + 1, last_worn = CURRENT_TIMESTAMP WHERE id = ?", (i,))

    conn.execute(
        """
        INSERT INTO outfits (title, item_ids, score, verdict, palette_json, stylist_notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("title", "Daily Outfit"),
            json.dumps(item_ids),
            payload.get("score", 85.0),
            payload.get("verdict", "STRONG"),
            json.dumps(payload.get("palette", {})),
            json.dumps(payload.get("notes", []))
        )
    )
    conn.commit()
    conn.close()
    return {"success": True}


# ---------------------------------------------------------------------------
# Analytics Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_wardrobe_stats():
    conn = db.get_conn()
    total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    total_outfits = conn.execute("SELECT COUNT(*) FROM outfits").fetchone()[0]
    
    cat_rows = conn.execute("SELECT category, COUNT(*) as count FROM items GROUP BY category").fetchall()
    categories = {r["category"]: r["count"] for r in cat_rows}

    color_rows = conn.execute("SELECT color_name, COUNT(*) as count FROM items GROUP BY color_name ORDER BY count DESC LIMIT 8").fetchall()
    colors = {r["color_name"] or "other": r["count"] for r in color_rows}

    most_worn_rows = conn.execute("SELECT id, name, category, wear_count, image_path FROM items ORDER BY wear_count DESC LIMIT 5").fetchall()
    most_worn = [dict(r) for r in most_worn_rows]
    conn.close()

    return {
        "total_items": total_items,
        "total_outfits": total_outfits,
        "categories": categories,
        "top_colors": colors,
        "most_worn": most_worn
    }


# ---------------------------------------------------------------------------
# Static Web Assets Mount
# ---------------------------------------------------------------------------

app.mount("/storage", StaticFiles(directory="storage"), name="storage")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
