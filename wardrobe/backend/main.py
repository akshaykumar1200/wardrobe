from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.database import engine, Base, SessionLocal
from backend.models import User
from backend.auth import hash_password, limiter
from backend.routers import auth_routes, items, uploads, images, admin, outfits, wears, cutout

app = FastAPI(title="Digital Wardrobe")

# Slowapi Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/healthz")
def healthz():
    """Liveness check that does not depend on the database."""
    return {"ok": True}

# CORS
origins = list(dict.fromkeys([
    settings.PUBLIC_ORIGIN,
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://192.168.29.222:8000"
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    # 1. Create database tables
    Base.metadata.create_all(bind=engine)

    # 2. Bootstrap Admin User if not exists
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL.strip().lower()).first()
        if not admin_user:
            admin_user = User(
                email=settings.ADMIN_EMAIL.strip().lower(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                display_name="Administrator",
                is_admin=1,
                is_active=1
            )
            db.add(admin_user)
            db.commit()
            print(f"Bootstrap Admin user created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


# Register Production API Routers
app.include_router(auth_routes.router)
app.include_router(items.router)
app.include_router(uploads.router)
app.include_router(cutout.router)
app.include_router(images.router)
app.include_router(admin.router)
app.include_router(outfits.router)
app.include_router(wears.router)

# Serve built frontend SPA (must come LAST after all /api routes)
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
