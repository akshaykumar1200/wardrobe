# Extraction flow

How an uploaded photo becomes wardrobe items. Two models do different jobs:

- **SegFormer** (`mattmdjaga/segformer_b2_clothes`) — human parsing. Says *which
  garment* a pixel belongs to. Only works when a person is in frame.
- **BiRefNet** (`ZhengPeng7/BiRefNet`) — class-agnostic matting. Says *where the
  subject ends*. Knows nothing about garments.

Neither alone is enough. SegFormer can't tell shoe from floor when they're the
same colour; BiRefNet can't tell a shirt from trousers.

---

## 1. Intake — `storage.validate_and_store_original`

```
raw bytes
  ├─ size ≤ MAX_UPLOAD_MB (10)                    else 413
  ├─ declared content-type in allowlist           else 415
  ├─ PIL decode + verify (header can be spoofed)  else 400
  ├─ width × height ≤ 50M (decompression bomb)    else 400
  ├─ EXIF transpose, then convert("RGB")          ← strips location metadata
  ├─ encode JPEG q=88
  └─ filename = sha256(encoded)[:32].jpg          ← identical photo = one file
```

Re-uploading the same photo hits the existing path, and the router returns the
items already extracted instead of paying for inference again.

## 2. Prepare — `segmenter.extract_garments`

```
source = img.convert("RGB")                 full resolution, kept for the crop
work   = resize(source, WORK_SIDE=1280)     everything below runs here
probs  = _predict(work)                     SegFormer @ INFERENCE_SIDE=1024,
                                            logits → bilinear upsample → softmax
certainty = probs.max(axis=0)
```

Masking at a bounded resolution keeps the logit tensor sane (upsampling straight
to 12MP allocated ~880MB). Crop pixels still come from `source`, so fabric
texture is not thrown away.

## 3. Branch — is there a person?

```
person pixels = labels ∈ {hair, face, legs, arms}
frac = person.mean()          conf = certainty[person].mean()

frac < 0.005  OR  conf < 0.65   →  FLAT-LAY
otherwise                       →  WORN
```

Measured: worn photos score **0.87–0.94** confidence here, a sneakers-on-a-bed
flat-lay scored **0.36**. Without this branch, SegFormer labelled those sneakers
"upper-clothes" at 0.66 and filed them as a Top.

---

## 4a. FLAT-LAY path

```
matte = matting.subject_matte(work)          BiRefNet

if matte is not None:                        ← preferred
    alpha = matte × 255                      true fractional alpha
    mask  = matte > 0.5
else:                                        ← offline / disabled fallback
    mask = _flatlay_mask(rgb)
      ├─ sample frame border (6%) as "the surface"
      ├─ k-means 4 clusters + per-cluster covariance
      ├─ Mahalanobis distance map over whole frame
      ├─ threshold = Otsu × 1.25, hysteresis grow at ×0.85
      ├─ pick blob by size × centredness (not just largest)
      └─ _colour_grow local repair, band 3%, veto at 0.6×weak
    alpha = _feather_alpha(mask)

guard: MIN_AREA_FRAC ≤ area ≤ FLATLAY_MAX_AREA (0.75)
result: ONE item, name "Untitled piece", category "other", + notice
```

Nothing here identifies *what* the garment is — there's no body to place it on —
so the user names and files it on the Review screen.

## 4b. WORN path

```
subject = matting.subject_matte(work)        once per photo, shared

for each garment group:
    topwear{4} · skirt{5} · trousers{6} · dress{7}
    shoes{9,10} · hat{1} · sunglasses{3} · bag{16}
```

Per group:

```
1  mask = _group_mask(probs, ids)
       sum group probabilities BEFORE argmax, then compare against the best
       class outside the group. Left-shoe and right-shoe otherwise split their
       probability and both lose to background on the sole. (+4.9%)

2  skip if area < MIN_AREA_FRAC (0.004 of frame — relative, not absolute)

3  _clean_mask
       binary_closing(5×5)
       keep largest component + any ≥12% of it, up to `parts`
         (parts=2 for shoes/trousers — the old "largest only" returned one shoe)
       binary_fill_holes
       NO binary_opening — it punched 22,615 holes through a garment and ate laces

4  _reject → too_small | covers_frame(>0.60) | scattered(fill<0.15)
             | low_confidence(<0.55)

5  score = certainty[mask].mean()
   if score < REFINE_BELOW (0.85):          ← only weak groups; Tops/Trousers
       _refine_mask → _colour_grow            sit at 0.97–0.99 and are left alone
         eligible = labels==background AND certainty ≤ 0.995
                    (only fixes pixels the model wrongly called background;
                     never touches another garment or a body part)
         band     = 1.1% of long side, via distance transform
         fit 3 foreground clusters (mask core) vs 5 background clusters (ring),
             compare max log-likelihood
         drop added components < 60px (ground speckle)
         purely additive — can grow an under-segmented mask, never shrink one
       re-run _reject

6  alpha = _feather_alpha(mask)
       signed distance field, ramp pushed 0.25px inside the boundary so
       semi-transparent pixels sample garment colour, not background.
       (The old code wrote alpha of only 0 or 255 — zero anti-aliasing — which
        is what made every cutout read as torn paper.)

7  if subject is not None:
       alpha ×= subject
       SegFormer keeps the garment-to-garment seams (matte ≈ 1 inside the body,
       so they're untouched); the silhouette against sky/ground/wall gets a real
       fractional alpha. Anything absorbed from outside the person — the
       balustrade behind the shoes — falls away here.

8  crop  = _compose_crop(source, alpha, bbox)
       RGB from the FULL-resolution original, alpha upscaled bicubic
9  color = _dominant_color(eroded core)
       modal 32-level colour bucket, then median — averaging a floral shirt
       returns mud
10 save_garment_crop
       cap OUTPUT_MAX_SIDE=1024, PNG optimize, sha256 content-hash filename
       (uncapped output previously wrote an 18.5MB PNG for one item)
```

## 5. Return

```json
{ "upload_id", "original_stored_name", "duplicate_of_existing",
  "notice", "candidates": [ { name, category, stored_name, color,
                              bytes, confidence, image_url } ] }
```

`confidence` is SegFormer's certainty about its own labelling — refinement and
matting improve the mask but do not change this number. `null` for flat-lays.

## 6. Review

User renames, recategorises, deletes, or manually adds. Only then do items
persist to the `items` table.

---

## Turning matting off

`MATTING_ENABLED=false` skips the ~220MB download and saves ~25s per photo.
Flat-lays fall back to the colour heuristic, worn garments keep the distance-
field alpha. Quality drops most on flat-lays and on silhouettes against
similar-coloured backgrounds.

## Known limits

- **Accessories never fire.** Hat/sunglasses/bag are mapped but produced nothing
  across the test set.
- **Shoes on a person sit at ~0.57 confidence.** This checkpoint is weak on
  shoes; neither more resolution (0.6% change from 512→1280) nor a zoomed second
  pass (much worse — the model needs a whole body) helps.
- **A dark wedge between close-together shoes** comes from SegFormer's raw mask,
  not from refinement.
- **Cost**: ~10–12s per photo without matting, ~35–40s with it, on 8 CPU threads.
