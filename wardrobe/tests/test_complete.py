"""Painting in what a hand or arm hid, on a synthetic photo (no ML weights loaded)."""
import io

import numpy as np
import pytest
from PIL import Image

from backend import flatten, segmenter
from backend.storage import capture_crops

SHIRT, SKIN, FILL = (40, 120, 90), (220, 170, 140), (1, 2, 3)
TOP, LEFT = 40, 50   # the shirt's top-left corner, so source (y, x) -> crop (y - TOP, x - LEFT)


def scene():
    """200x200: a shirt with a hand cutting into its hem, a hand lying on its
    front, a hand hanging below it, and a neckline over the neck."""
    labels = np.zeros((200, 200), np.uint8)
    labels[10:40, 90:110] = 11            # face
    labels[TOP:160, LEFT:150] = 4         # shirt
    labels[40:50, 95:105] = 11            # neckline: neck skin, a real opening
    labels[80:95, 70:85] = 14             # hand lying on the front
    labels[140:176, 95:105] = 14          # hand over the hem, hanging below it
    rgb = np.full((200, 200, 3), 255, np.uint8)
    rgb[labels == 4] = SHIRT
    rgb[np.isin(labels, (11, 14))] = SKIN
    probs = np.full((18, 200, 200), 0.03 / 17, np.float32)
    for k in np.unique(labels):
        probs[k][labels == k] = 0.97
    return Image.fromarray(rgb), probs


@pytest.fixture
def photo(monkeypatch):
    img, probs = scene()
    monkeypatch.setattr(segmenter, "_predict", lambda image: probs)
    monkeypatch.setattr(segmenter.matting, "subject_matte", lambda image: None)
    monkeypatch.setattr(flatten, "_load_lama", lambda: None)
    monkeypatch.setattr(flatten, "_lama_fill",
                        lambda rgb, holes: np.where(holes[..., None], np.uint8(FILL), rgb))
    return img


def top(img, complete):
    with capture_crops() as captured:
        result = segmenter.extract_garments(img, 0, complete=complete)
    item = next(i for i in result["items"] if i["category"] == "topwear")
    return item, np.array(Image.open(io.BytesIO(captured[item["stored_name"]])))


def px(crop, y, x):
    return crop[y - TOP, x - LEFT]


def test_hidden_parts_are_painted_and_real_pixels_kept(photo):
    item, crop = top(photo, complete=True)
    assert tuple(px(crop, 150, 100)) == FILL + (255,)       # notch the hand cut into the hem
    assert tuple(px(crop, 87, 77)) == FILL + (255,)         # hand lying on the front
    assert tuple(px(crop, 100, 120)) == SHIRT + (255,)      # real fabric untouched
    assert px(crop, 45, 100)[3] == 0                        # the neckline stays open
    assert crop.shape[0] == 160 - TOP                       # the hand below the hem is not shirt
    assert item["color"] == "#{:02x}{:02x}{:02x}".format(*SHIRT)
    assert 0 < item["filled"] < 0.1


def test_without_complete_nothing_changes(photo):
    item, crop = top(photo, complete=False)
    assert px(crop, 150, 100)[3] == 0                       # notch stays a gap
    assert tuple(px(crop, 87, 77)) == SKIN + (255,)         # the hand shows, as before
    assert "filled" not in item


def test_missing_lama_falls_back_to_the_plain_cut_out(photo, monkeypatch):
    def missing():
        raise flatten.ModelMissing()
    monkeypatch.setattr(flatten, "_load_lama", missing)
    _, plain = top(photo, complete=False)
    item, crop = top(photo, complete=True)
    assert np.array_equal(crop, plain)
    assert "filled" not in item


def test_too_much_hidden_is_left_alone(photo, monkeypatch):
    monkeypatch.setattr(segmenter, "COMPLETE_MAX_FRAC", 0.001)
    item, crop = top(photo, complete=True)
    assert px(crop, 150, 100)[3] == 0
    assert item["filled"] == 0.0


def labelled(labels):
    probs = np.full((18, *labels.shape), 0.03 / 17, np.float32)
    for k in np.unique(labels):
        probs[k][labels == k] = 0.97
    rgb = np.full((*labels.shape, 3), 255, np.uint8)
    rgb[labels == 7] = SHIRT
    rgb[np.isin(labels, (11, 12, 13))] = SKIN
    return Image.fromarray(rgb), probs


@pytest.mark.parametrize("waist_up", [True, False])
def test_waist_up_dress_is_a_top(monkeypatch, waist_up):
    labels = np.zeros((200, 200), np.uint8)
    labels[5:35, 90:110] = 11                     # face
    if waist_up:
        labels[40:200, 50:150] = 7                # "Dress" cut off by the frame bottom
    else:
        labels[40:140, 50:150] = 7                # a real dress, legs below it
        labels[140:195, 75:95] = 12
        labels[140:195, 105:125] = 13
    img, probs = labelled(labels)
    monkeypatch.setattr(segmenter, "_predict", lambda image: probs)
    monkeypatch.setattr(segmenter.matting, "subject_matte", lambda image: None)
    with capture_crops():
        items = segmenter.extract_garments(img, 0)["items"]
    assert [(i["name"], i["category"]) for i in items] == (
        [("Top", "topwear")] if waist_up else [("Dress", "other")])


def test_tiny_hidden_part_skips_lama(photo, monkeypatch):
    monkeypatch.setattr(segmenter, "COMPLETE_MIN_FRAC", 0.5)
    monkeypatch.setattr(flatten, "_lama_fill", lambda rgb, holes: pytest.fail("LaMa ran for a tiny gap"))
    item, crop = top(photo, complete=True)
    assert px(crop, 150, 100)[3] == 0
    assert item["filled"] == 0.0
