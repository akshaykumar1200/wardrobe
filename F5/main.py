import json
import uuid
import time
import asyncio
from pathlib import Path
from PIL import Image
import io

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import db
from segmenter import extract_garments
from outfit_color import rank_combinations, score_outfit
from pattern import analyze_garment

app = FastAPI(title="OOTD — Personal Digital Wardrobe")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORIGINALS_DIR = Path("storage/originals")
ITEMS_DIR = Path("storage/items")

ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
ITEMS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- 24-Hour Orphan Cutout Cleanup Helper ----------

def cleanup_orphan_files(max_age_seconds: int = 86400) -> int:
    """
    Deletes files in storage/items and storage/originals that:
    1. Are older than max_age_seconds (default: 24 hours)
    2. Are NOT referenced by any active wardrobe item in SQLite.
    """
    now = time.time()
    deleted_count = 0
    
    try:
        registered_paths = db.get_all_registered_image_paths()
    except Exception as e:
        print(f"[Cleanup] Could not fetch registered paths: {e}")
        return 0

    # 1. Clean unconfirmed item cutouts
    if ITEMS_DIR.exists():
        for file in ITEMS_DIR.glob("*.*"):
            rel_path = f"storage/items/{file.name}"
            if rel_path not in registered_paths:
                file_age = now - file.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        print(f"[Cleanup] Error deleting {file}: {e}")

    # 2. Clean old original staging photos
    if ORIGINALS_DIR.exists():
        for file in ORIGINALS_DIR.glob("*.*"):
            file_age = now - file.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"[Cleanup] Error deleting {file}: {e}")

    if deleted_count > 0:
        print(f"[Cleanup] Purged {deleted_count} orphan files older than 24 hours.")
    return deleted_count


async def periodic_cleanup_task():
    """Background loop that runs orphan cleanup every 6 hours."""
    while True:
        try:
            cleanup_orphan_files(max_age_seconds=86400)
        except Exception as e:
            print(f"[Cleanup Task Error]: {e}")
        await asyncio.sleep(21600)  # 6 hours


@app.on_event("startup")
def startup():
    db.init_db()
    # Run initial cleanup on startup
    cleanup_orphan_files(max_age_seconds=86400)
    # Schedule background cleanup loop
    asyncio.create_task(periodic_cleanup_task())


# ---------- Authentication Dependencies ----------

def get_current_user(request: Request, authorization: str | None = Header(None)) -> dict | None:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif "ootd_token" in request.cookies:
        token = request.cookies["ootd_token"]

    if token:
        user = db.get_user_by_token(token)
        if user:
            return user
    return None


def require_user(current_user: dict | None = Depends(get_current_user)) -> dict:
    if not current_user:
        raise HTTPException(401, "Please sign in or create an account to continue.")
    return current_user


# ---------- Auth Endpoints ----------

@app.post("/api/auth/register")
def register(payload: dict = Body(...)):
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    if not username:
        raise HTTPException(400, "Please enter a username.")
    if not password:
        raise HTTPException(400, "Please enter a password.")

    try:
        user = db.create_user(username, password)
        resp = JSONResponse({"ok": True, "user": {"id": user["id"], "username": user["username"]}, "token": user["token"]})
        resp.set_cookie("ootd_token", user["token"], httponly=True, max_age=86400 * 30, samesite="lax")
        return resp
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Registration error: {e}")


@app.post("/api/auth/login")
def login(payload: dict = Body(...)):
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    if not username:
        raise HTTPException(400, "Please enter your username.")
    if not password:
        raise HTTPException(400, "Please enter your password.")

    user, status = db.authenticate_user(username, password)
    if status == "user_not_found":
        raise HTTPException(404, f"Account '{username}' not found. Please click 'Create Account' to register.")
    elif status == "wrong_password":
        raise HTTPException(401, "Incorrect password. Please check and try again.")

    resp = JSONResponse({"ok": True, "user": {"id": user["id"], "username": user["username"]}, "token": user["token"]})
    resp.set_cookie("ootd_token", user["token"], httponly=True, max_age=86400 * 30, samesite="lax")
    return resp


@app.post("/api/auth/logout")
def logout(request: Request, authorization: str | None = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif "ootd_token" in request.cookies:
        token = request.cookies["ootd_token"]

    if token:
        db.logout_user(token)

    resp = JSONResponse({"ok": True})
    resp.delete_cookie("ootd_token")
    return resp


@app.get("/api/auth/me")
def me(current_user: dict | None = Depends(get_current_user)):
    if not current_user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": current_user}


# ---------- Upload & Extract (Requires User) ----------

@app.post("/api/extract")
async def extract(file: UploadFile = File(...), current_user: dict = Depends(require_user)):
    """Segment an uploaded photo with SegFormer + BiRefNet. Requires authenticated user."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")

    original_name = f"{uuid.uuid4().hex}.jpg"
    (ORIGINALS_DIR / original_name).write_bytes(raw)

    try:
        garments = extract_garments(raw)
    except Exception as e:
        raise HTTPException(500, f"Segmentation failed: {e}")

    if not garments:
        return {"garments": [], "message": "No garments detected"}

    return {"garments": garments}


# ---------- Wardrobe Items (Strictly Protected) ----------

@app.post("/api/items")
async def create_item(payload: dict = Body(...), current_user: dict = Depends(require_user)):
    """Save user-confirmed garment scoped to current_user."""
    conn = db.get_conn()
    colors_json = json.dumps(payload.get("colors", []))
    cur = conn.execute(
        """
        INSERT INTO items (user_id, category, image_path, color, color_name, colors_json, pattern, pattern_scale, area, confidence, label) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_user["id"],
            payload["category"],
            payload["path"],
            payload.get("color", "#808080"),
            payload.get("color_name"),
            colors_json,
            payload.get("pattern", "solid"),
            payload.get("scale", "none"),
            payload.get("pixels", 0),
            payload.get("confidence", 1.0),
            payload.get("label", payload["category"].capitalize()),
        ),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return {"id": item_id, "path": payload["path"]}


@app.get("/api/items")
def list_items(category: str | None = None, current_user: dict | None = Depends(get_current_user)):
    """List only the items belonging to current_user. If unauthenticated, returns []."""
    if not current_user:
        return []

    conn = db.get_conn()
    if category and category != "all":
        rows = conn.execute(
            "SELECT * FROM items WHERE user_id=? AND category=? ORDER BY created_at DESC",
            (current_user["id"], category)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM items WHERE user_id=? ORDER BY created_at DESC",
            (current_user["id"],)).fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        if d.get("colors_json"):
            try:
                d["colors"] = json.loads(d["colors_json"])
            except Exception:
                d["colors"] = [{"hex": d["color"] or "#808080", "name": d.get("color_name") or "grey", "share": 1.0}]
        else:
            d["colors"] = [{"hex": d["color"] or "#808080", "name": d.get("color_name") or "grey", "share": 1.0}]
        items.append(d)
    return items


@app.put("/api/items/{item_id}")
def update_item(item_id: int, payload: dict = Body(...), current_user: dict = Depends(require_user)):
    conn = db.get_conn()
    conn.execute(
        "UPDATE items SET category = ?, label = ?, color = ? WHERE id = ? AND user_id = ?",
        (payload.get("category"), payload.get("label"), payload.get("color"), item_id, current_user["id"])
    )
    conn.commit()
    conn.close()
    return {"updated": item_id}


@app.post("/api/items/manual")
async def create_manual_item(
    file: UploadFile = File(...),
    category: str = "upper",
    label: str | None = None,
    color: str = "#4a6b5d",
    current_user: dict = Depends(require_user)
):
    """Upload a manual garment image directly into the user's private wardrobe."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")

    filename = f"{uuid.uuid4().hex}.png"
    item_path = ITEMS_DIR / filename
    item_path.write_bytes(raw)

    web_path = f"/storage/items/{filename}"

    try:
        img = Image.open(io.BytesIO(raw))
        analysis = analyze_garment(img, category=category, name=label or category.capitalize())
        color_hex = analysis["color_hex"]
        color_name = analysis["color_name"]
        colors_json = json.dumps(analysis["colors"])
        pattern = analysis["pattern"]
        pattern_scale = analysis["scale"]
    except Exception:
        color_hex = color
        color_name = "custom"
        colors_json = "[]"
        pattern = "solid"
        pattern_scale = "none"

    conn = db.get_conn()
    cur = conn.execute(
        """
        INSERT INTO items (user_id, category, image_path, color, color_name, colors_json, pattern, pattern_scale, label) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (current_user["id"], category, web_path, color_hex, color_name, colors_json, pattern, pattern_scale, label or category.capitalize()),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return {"id": item_id, "path": web_path}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, current_user: dict = Depends(require_user)):
    """Delete an item only if it belongs to current_user."""
    conn = db.get_conn()
    row = conn.execute("SELECT image_path FROM items WHERE id=? AND user_id=?",
                       (item_id, current_user["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found or unauthorized")

    f = Path("." + row["image_path"])
    if f.exists():
        try:
            f.unlink()
        except Exception:
            pass

    conn.execute("DELETE FROM items WHERE id=? AND user_id=?", (item_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"deleted": item_id}


# ---------- Outfit Suggestion (User-Scoped) ----------

@app.get("/api/suggest")
def suggest(current_user: dict | None = Depends(get_current_user)):
    if not current_user:
        return {"outfit": [], "score": None, "verdict": None, "notes": [], "palette": None}

    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM items WHERE user_id=?", (current_user["id"],)).fetchall()]
    conn.close()

    if not rows:
        return {"outfit": [], "score": None, "verdict": None, "notes": [], "palette": None}

    wardrobe = []
    for r in rows:
        if r.get("colors_json"):
            try:
                r["colors"] = json.loads(r["colors_json"])
            except Exception:
                r["colors"] = [{"hex": r.get("color") or "#808080", "name": r.get("color_name") or "grey", "share": 1.0}]
        else:
            r["colors"] = [{"hex": r.get("color") or "#808080", "name": r.get("color_name") or "grey", "share": 1.0}]
        wardrobe.append(r)

    ranked = rank_combinations(wardrobe, top_n=5)
    if not ranked:
        return {"outfit": [], "score": None, "verdict": None, "notes": [], "palette": None}

    top_sug = ranked[0]
    return {
        "outfit": top_sug["items"],
        "score": top_sug["score"],
        "verdict": top_sug["verdict"],
        "notes": top_sug["notes"],
        "palette": top_sug["palette"],
        "all_suggestions": ranked
    }


@app.post("/api/wear")
def mark_worn(payload: dict = Body(...), current_user: dict = Depends(require_user)):
    ids = payload.get("item_ids", [])
    conn = db.get_conn()
    for i in ids:
        conn.execute(
            "UPDATE items SET wear_count = wear_count + 1, "
            "last_worn = CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (i, current_user["id"]))

    conn.execute(
        """
        INSERT INTO outfits (user_id, item_ids, score, verdict, palette_json, stylist_notes, worn_on) 
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            current_user["id"],
            json.dumps(ids),
            payload.get("score"),
            payload.get("verdict"),
            json.dumps(payload.get("palette", {})),
            json.dumps(payload.get("notes", []))
        )
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Static Files ----------
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
