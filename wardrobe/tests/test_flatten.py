"""Synthetic, deterministic coverage for flat view (no ML weights loaded)."""
import io
import time
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import flatten
from backend.auth import create_session, hash_password
from backend.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import Item, Upload, User


def synthetic(size=(220, 260), touch_bottom=False):
    w, h = size
    labels = np.zeros((h, w), np.uint8)
    im = Image.new("RGB", size, (35, 45, 55))
    draw = ImageDraw.Draw(im)
    hem = h-1 if touch_bottom else int(h*.88)
    # Shirt shoulders, sleeves and straight torso.
    poly = [(w*.42,h*.15),(w*.58,h*.15),(w*.66,h*.21),(w*.88,h*.36),
            (w*.78,h*.50),(w*.69,h*.43),(w*.68,hem),(w*.32,hem),
            (w*.31,h*.43),(w*.22,h*.50),(w*.12,h*.36),(w*.34,h*.21)]
    draw.polygon(poly, fill=(190, 45, 30))
    # Neck cut-in reads as the model's garment edge; face and arm labels are separate.
    draw.rectangle((int(w*.44), int(h*.10), int(w*.56), int(h*.20)), fill=(35,45,55))
    # Distinctive real-fabric stripe.
    draw.rectangle((int(w*.48),int(h*.35),int(w*.51),int(h*.73)), fill=(20,220,240))
    # IDs are supplied by a fake model config in each test.
    m = Image.new("L", size); md = ImageDraw.Draw(m); md.polygon(poly, fill=1)
    md.rectangle((int(w*.44), int(h*.10), int(w*.56), int(h*.20)), fill=0)
    labels[np.asarray(m)>0] = 4
    labels[int(h*.02):int(h*.12),int(w*.45):int(w*.55)] = 2
    # Arms touch just outside sleeve edge to create cuff contact.
    labels[int(h*.30):int(h*.49),int(w*.08):int(w*.18)] = 14
    labels[int(h*.30):int(h*.49),int(w*.82):int(w*.92)] = 15
    return im, labels


def patch_segmenter(monkeypatch, labels):
    names={0:"Background",2:"Hair",4:"Upper-clothes",7:"Dress",11:"Face",14:"Left-arm",15:"Right-arm"}
    monkeypatch.setattr(flatten.segmenter, "model", SimpleNamespace(config=SimpleNamespace(id2label=names)))
    probs=np.zeros((16,*labels.shape),np.float32)
    for k in range(16): probs[k][labels==k]=1
    monkeypatch.setattr(flatten.segmenter,"_predict",lambda image: probs)


def test_landmarks_and_frame_bottom_extension(monkeypatch):
    photo, labels=synthetic(touch_bottom=True); patch_segmenter(monkeypatch, labels)
    probs=np.zeros((16,*labels.shape)); probs[0]=1; probs[4,labels==4]=1; probs[14,labels==14]=1; probs[15,labels==15]=1
    mask=labels==4; arms=np.isin(labels,[14,15])
    lm=flatten._landmarks(mask,arms,False)
    assert lm["neck_l"][1] < 60 and lm["neck_r"][1] < 60
    assert lm["cuff_outer_l"][0] < lm["shoulder_l"][0]
    assert lm["cuff_outer_r"][0] > lm["shoulder_r"][0]
    assert lm["armpit_l"][1] > lm["shoulder_l"][1]
    assert lm["hem_c"][1] >= labels.shape[0]


def test_arm_contacts_below_sleeve_opening_are_ignored():
    photo, labels = synthetic()
    mask = labels == 4
    arms = np.zeros_like(mask)
    h, w = mask.shape
    # Arms touch the shirt at the sleeve openings and continue beside the body
    # to the hem, where hands overlap the lower front.
    arms[int(h*.29):int(h*.84), int(w*.30):int(w*.35)] = True
    arms[int(h*.29):int(h*.84), int(w*.65):int(w*.70)] = True
    arms[int(h*.76):int(h*.86), int(w*.30):int(w*.70)] = True
    lm = flatten._landmarks(mask, arms, False)
    for side in ("l", "r"):
        assert lm[f"armpit_{side}"][1] < h*.40
        assert abs(lm[f"armpit_{side}"][1] - h*.29) < h*.10


def test_uneven_hem_uses_bottom_band_width():
    _, labels = synthetic()
    mask = labels == 4
    h, w = mask.shape
    # Cut a deep notch into the middle while retaining the broad outer hem.
    mask[int(h*.78):, int(w*.43):int(w*.57)] = False
    lm = flatten._landmarks(mask, np.isin(labels, [14, 15]), False)
    bottom_band = np.where(mask & (np.indices(mask.shape)[0] >= np.where(mask)[0].max() - flatten.HEM_BAND * (np.where(mask)[0].max()-np.where(mask)[0].min()+1)))[1]
    assert lm["hem_r"][0] - lm["hem_l"][0] >= .70 * (bottom_band.max()-bottom_band.min())


def test_colour_is_preserved_after_flattening(monkeypatch):
    photo, labels = synthetic()
    patch_segmenter(monkeypatch, labels)
    arr = np.asarray(photo).copy()
    arr[labels == 4] = (40, 120, 90)
    photo = Image.fromarray(arr)
    monkeypatch.setattr(flatten, "_lama_fill", lambda rgb, holes: rgb)
    data, _ = flatten.flatten_top(photo)
    out = np.asarray(Image.open(io.BytesIO(data)))
    real = (out[:, :, 3] > 0) & np.all(out[:, :, :3] == (40, 120, 90), axis=2)
    # Interpolation edges can differ by a few values; compare the median real fabric.
    fabric = out[(out[:, :, 3] > 0) & (out[:, :, 0] > 20)]
    assert np.all(np.abs(np.median(fabric, axis=0)[:3] - (40, 120, 90)) <= 12)


def test_folded_warp_is_refused():
    class ReversingWarp:
        def __call__(self, points):
            return np.column_stack((-points[:, 0], points[:, 1]))
    silhouette = np.ones((40, 40), bool)
    with pytest.raises(flatten.NotSuitable, match="Couldn't map this photo"):
        flatten._check_warp_folds(ReversingWarp(), silhouette)


def test_no_garment_is_refused(monkeypatch):
    labels=np.zeros((64,64),np.uint8); patch_segmenter(monkeypatch,labels)
    with pytest.raises(flatten.NotSuitable, match="No top"):
        flatten.flatten_top(Image.new("RGB",(64,64)))


def test_warp_preserves_real_stripe_and_fills_holes(monkeypatch):
    photo, labels=synthetic(); patch_segmenter(monkeypatch,labels)
    def fill(rgb, holes):
        out=rgb.copy(); out[holes]=(12,34,56); return out
    monkeypatch.setattr(flatten,"_lama_fill",fill)
    data, info=flatten.flatten_top(photo)
    out=Image.open(io.BytesIO(data))
    assert out.mode=="RGBA" and out.size==(flatten.CANVAS,flatten.CANVAS)
    arr=np.asarray(out)
    assert info["real_fraction"] > 0
    assert np.any((arr[:,:,1]>150)&(arr[:,:,2]>150)&(arr[:,:,3]>0)), "real stripe disappeared"
    assert np.any(np.all(arr[:,:,:3]==(12,34,56),axis=2)&(arr[:,:,3]>0)), "holes were not filled"


@pytest.fixture
def api(tmp_path, monkeypatch):
    dbfile=tmp_path/"flat.db"
    engine=create_engine(f"sqlite:///{dbfile}",connect_args={"check_same_thread":False})
    Session=sessionmaker(autocommit=False,autoflush=False,bind=engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings,"STORAGE_ROOT",str(tmp_path/"storage"))
    def override():
        db=Session()
        try: yield db
        finally: db.close()
    prev=app.dependency_overrides.get(get_db); app.dependency_overrides[get_db]=override
    db=Session(); user=User(email="flat@example.com",password_hash=hash_password("Password123!")); db.add(user); db.commit(); db.refresh(user)
    token=create_session(db,user.id,"test")
    upload=Upload(user_id=user.id,stored_name="original.jpg",bytes=1); db.add(upload); db.commit(); db.refresh(upload)
    top=Item(user_id=user.id,name="T",category="topwear",stored_name="shirt.png",upload_id=upload.id)
    pants=Item(user_id=user.id,name="P",category="bottomwear",stored_name="pants.png")
    db.add_all([top,pants]); db.commit(); db.refresh(top); db.refresh(pants)
    other=User(email="other@example.com",password_hash=hash_password("Password123!")); db.add(other); db.commit(); db.refresh(other)
    otheritem=Item(user_id=other.id,name="Other",category="topwear",stored_name="other.png"); db.add(otheritem); db.commit(); db.refresh(otheritem)
    orig=tmp_path/"storage"/"users"/str(user.id)/"originals"; orig.mkdir(parents=True); Image.new("RGB",(8,8)).save(orig/"original.jpg")
    c=TestClient(app); c.cookies.set("session",token)
    yield c, top.id, pants.id, otheritem.id, tmp_path/"storage"/"users"/str(user.id)/"items"
    if prev is None: app.dependency_overrides.pop(get_db,None)
    else: app.dependency_overrides[get_db]=prev
    Base.metadata.drop_all(engine); engine.dispose()


def test_flat_endpoint_errors_success_replace_and_image_route(api, monkeypatch):
    c, top, pants, other, items=api
    assert c.post(f"/api/items/{pants}/flat").status_code==400
    assert c.post(f"/api/items/{other}/flat").status_code==404
    # Remove upload source to exercise the missing-original response.
    source=items.parent/"originals"/"original.jpg"; source.unlink()
    assert c.post(f"/api/items/{top}/flat").status_code==400
    Image.new("RGB",(8,8)).save(source)
    count=[0]
    def fake(photo):
        count[0]+=1
        return (f"png{count[0]}".encode(),{"real_fraction":.9,"hem_extended":False,"seconds":.1})
    monkeypatch.setattr(flatten,"flatten_top",fake)
    a=c.post(f"/api/items/{top}/flat"); b=c.post(f"/api/items/{top}/flat")
    assert a.status_code==200 and a.json()["stored_name"]=="flat-shirt.png"
    assert b.status_code==200 and (items/"flat-shirt.png").read_bytes()==b"png2"
    assert c.get("/api/images/item/flat-shirt.png").content==b"png2"


def test_sweeper_retains_flat_variant_for_kept_item(monkeypatch):
    from backend import storage
    captured=[]
    monkeypatch.setattr(storage.crops,"old_names",lambda *a:{"flat-X":12,"flat-Y":14})
    monkeypatch.setattr(storage.crops,"delete",lambda db,user,name:captured.append(name))
    storage.sweep_orphan_crops(1,{"X"},object())
    assert captured==["flat-Y"]


def test_delete_removes_flat_crop(api, monkeypatch):
    c, top, _, _, items=api
    # A top crop deletion removes its associated flat derivative too.
    items.mkdir(parents=True, exist_ok=True)
    (items/"shirt.png").write_bytes(b"shirt"); (items/"flat-shirt.png").write_bytes(b"flat")
    assert c.delete(f"/api/items/{top}").status_code==200
    assert not (items/"flat-shirt.png").exists()
