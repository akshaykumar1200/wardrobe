---
id: flat-view-fix
files: [wardrobe/backend/flatten.py, wardrobe/tests/test_flatten.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
`backend/flatten.py` passes its synthetic tests but produces garbage on real
photos: swirled fabric, wing-shaped sleeves, a narrow body, and neon colours.
The landmarks were drawn on two real photos and the causes are confirmed.
Fix these four, add a guard, and add tests that would have caught each one.

## 1. Cuff and armpit points land on the hands, not the sleeve opening
`_landmarks` takes **every** garment pixel touching an arm. On a real worn
photo the arms hang alongside the torso down to the pockets, so that contact
runs from the sleeve all the way to the hem, and "nearest to `cx`" picks a
point at the **hands, at hem level**. Measured on a real photo: inner cuff /
armpit at y=948 with the hem at y=997, when the sleeve opening is at about
y=730.

Fix: the sleeve opening is where each arm **starts**. Per side, take the
largest arm component on that side and its top y (`arm_top`). Only use
garment-arm contact pixels with `y <= arm_top + CUFF_BAND * bh`, with
`CUFF_BAND = 0.08`. Outer = farthest from `cx` in that band, inner = nearest.
Contact below the band is the arm lying along the body and must never be used.
Keep the existing fallback for a side with no arm.

## 2. Hem points bunch in the middle
"Columns whose bottom is within 3% of the lowest bottom" picks a narrow
central strip, because the real hem is uneven and hands interrupt it.
Measured: hem L and R only 77 px apart on a shirt about 280 px wide.

Fix: take garment pixels with `y >= y1 - HEM_BAND * bh` (`HEM_BAND = 0.12`).
Hem L x = 5th percentile of their x, hem R x = 95th percentile, both at the
garment's bottom y (plus the existing extension when the hem touches the
frame). Hem centre stays at `cx`.

## 3. Neon colours: `_lab_even` is mathematically wrong
It scales **linear RGB** and then multiplies it by the **XYZ-to-RGB matrix**,
but that data was never converted to XYZ, so every colour is distorted.

Replace the whole function with a correction on linear luminance and nothing
else:
- `lin` = sRGB decoded to linear
- `Y = lin @ [0.2126, 0.7152, 0.0722]`
- `illum` = Gaussian blur of `Y * valid` divided by blur of `valid` (same sigma)
- `gain = clip(median(Y[valid]) / illum, 0.5, 2.0)`; `lin *= gain[..., None]`
- encode back to sRGB

No XYZ or Lab matrices at all. Keep the one-line comment that this cannot
remove sharp cast shadows.

## 4. The target shape makes wings
The canonical armpit sits out on the sleeve, so the body side runs diagonally
out to it. Rebuild the canonical sleeve and armpit:
- sleeve direction `d` = outward and `SLEEVE_ANGLE_DEG` below horizontal; the
  perpendicular `n` points down and inward
- cuff outer = shoulder + `sleeve * d`; cuff inner = cuff outer + `cuff * n`
- add a **target-only** armpit at `x = c +/- bodyw/2`, `y = shoulder_y +
  armhole`, where `armhole` = the source armpit's height below the source
  shoulder, clipped to `[0.12, 0.35] * bodylen`
- polygon order: neck L, shoulder L, cuff outer L, cuff inner L, **armpit L**,
  body L, hem L, hem centre, hem R, body R, **armpit R**, cuff inner R, cuff
  outer R, shoulder R, neck R, collar centre
- the target armpit is a polygon vertex only. **Do not** pair it with a
  source point in the warp; the warp keeps using the existing landmark pairs.

## 5. Guard: refuse instead of producing swirls
After fitting the thin-plate spline, evaluate it on a grid of points inside
the silhouette (every 8 px) and compute the Jacobian determinant by finite
differences. If it is **<= 0 for more than 1%** of those points, the mapping
folds the image onto itself. Raise
`NotSuitable("Couldn't map this photo to a flat shape cleanly. A front-facing
photo with arms slightly away from the body works best.")`.

## Tests to add (synthetic, no real models, same style as the existing ones)
- **arms down to the hem**: a T-shirt with arm rectangles running from the
  sleeve openings down past the hem, with "hands" touching the shirt's lower
  front. Cuff inner / armpit must be within 10% of the shirt height of the
  sleeve opening, never near the hem.
- **uneven hem**: a hem with a notch in the middle. Hem L and R must be at
  least 70% of the shirt's bottom-band width apart.
- **colour preserved**: a shirt of one flat colour (for example RGB 40,120,90)
  with the LaMa fill monkeypatched; the median colour of real pixels in the
  output must stay within 12 per channel of the input. The current code fails
  this test badly, which is what proves it would have caught the neon bug.
- **fold guard**: landmarks arranged to cross (for example cuffs swapped left
  and right) must raise `NotSuitable`, not return an image.

## Done when
`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes all 58
existing tests plus the new ones, none skipped.

## Do not
- Do not change `routers/`, `storage.py`, `config.py`, the frontend or the schema.
- Do not add a dependency or load any real model in tests.
- Do not loosen any existing sanity check to make a test pass.
