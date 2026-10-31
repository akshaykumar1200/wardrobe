"""Crop byte storage, selected by the application's configured database."""

from pathlib import Path
from datetime import datetime, timedelta

from backend.config import settings
from backend.models import Blob


def _on_disk(db) -> bool:
    """SQLite keeps crops on disk; Postgres keeps them in the blobs table.

    Decided from the session's own database, not the configured one: a session
    bound elsewhere (a test, a migration) must not read a store it never wrote.
    """
    return db.get_bind().dialect.name == "sqlite"


def _path(user_id: int, stored_name: str) -> Path | None:
    user_base = (Path(settings.STORAGE_ROOT).resolve() / "users" / str(user_id)).resolve()
    path = (user_base / "items" / stored_name).resolve()
    if not path.is_relative_to(user_base):
        return None
    return path


def put(db, user_id: int, stored_name: str, data: bytes) -> int:
    size = len(data)
    if _on_disk(db):
        path = _path(user_id, stored_name)
        if path is None:
            raise ValueError("Bad storage path")
        if path.exists():
            return path.stat().st_size
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return size

    existing = db.get(Blob, (user_id, stored_name))
    if existing is not None:
        return existing.bytes
    db.add(Blob(user_id=user_id, stored_name=stored_name, data=data, bytes=size))
    # Sessions run with autoflush off, so without this the blob stays invisible to
    # every read in the same request -- put then get returned None.
    db.flush()
    return size


def get(db, user_id: int, stored_name: str) -> bytes | None:
    if _on_disk(db):
        path = _path(user_id, stored_name)
        return path.read_bytes() if path is not None and path.is_file() else None
    blob = db.get(Blob, (user_id, stored_name))
    return blob.data if blob is not None else None


def exists(db, user_id: int, stored_name: str) -> bool:
    if _on_disk(db):
        path = _path(user_id, stored_name)
        return path is not None and path.is_file()
    return db.get(Blob, (user_id, stored_name)) is not None


def delete(db, user_id: int, stored_name: str) -> None:
    if _on_disk(db):
        path = _path(user_id, stored_name)
        if path is not None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return
    blob = db.get(Blob, (user_id, stored_name))
    if blob is not None:
        db.delete(blob)
        db.flush()


def names(db, user_id: int) -> set[str]:
    if _on_disk(db):
        user_base = (Path(settings.STORAGE_ROOT).resolve() / "users" / str(user_id)).resolve()
        items_dir = user_base / "items"
        if not items_dir.is_dir():
            return set()
        return {
            path.name for path in items_dir.iterdir()
            if path.is_file() and path.resolve().is_relative_to(user_base)
        }
    return {
        name for (name,) in db.query(Blob.stored_name).filter(Blob.user_id == user_id).all()
    }


def old_names(db, user_id: int, age_seconds: int) -> dict[str, int]:
    """Return stale crop names and byte sizes using the store's own timestamps."""
    if _on_disk(db):
        cutoff = __import__("time").time() - age_seconds
        stale = {}
        for name in names(db, user_id):
            path = _path(user_id, name)
            if path is None:
                continue
            try:
                stat = path.stat()
                if stat.st_mtime <= cutoff:
                    stale[name] = stat.st_size
            except OSError:
                continue
        return stale

    cutoff = datetime.utcnow() - timedelta(seconds=age_seconds)
    return {
        blob.stored_name: blob.bytes
        for blob in db.query(Blob).filter(
            Blob.user_id == user_id,
            Blob.created_at <= cutoff,
        ).all()
    }
