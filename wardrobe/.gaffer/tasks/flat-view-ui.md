---
id: flat-view-ui
files: [wardrobe/frontend/src/pages/Closet.jsx]
test: cd wardrobe/frontend && npm run build
effort: medium
sandbox: full
timeout: 30
---
Add a **"Flat view"** action to tops in the closet. The backend endpoint is
being built in parallel; this is its contract:

- `POST /api/items/{id}/flat` (no body). Takes **30-90 seconds** on this laptop.
- 200 → `{"stored_name": "flat-...", "real_fraction": 0.9, "hem_extended": true, "seconds": 41.2}`
- Errors are JSON `{"detail": "..."}`: 400 (not a top, or no original photo on
  this server), 404, 422 (photo not suitable, with a plain-English reason),
  429 (too many requests), 503 (feature unavailable on this server).
- The image is then served by the existing `GET /api/images/item/{stored_name}`.

Read `frontend/src/pages/Closet.jsx` and `frontend/src/api.js` first, and
match the existing card, button, modal and palette exactly. The edit modal
already in this file is the pattern to copy.

## Behaviour
- Show a small **"Flat view"** button only on items whose
  `category === "topwear"`, next to the existing card actions, same style.
- Clicking opens a modal that calls the endpoint with the existing `api()`
  helper and shows **"Making a flat view from your photo... this takes about
  a minute"** while it runs. Disable the button while running; never send a
  second request at the same time.
- On success show the **original cut-out and the flat view side by side**,
  loading the flat image from `/api/images/item/<stored_name>?v=<Date.now()>`
  so a regenerated image is not served from the browser cache.
- Under the images always show this label, small and muted:
  **"AI-adjusted: your photo's real pixels rearranged into a flat shape.
  Areas hidden in the photo were filled in."** Add **"The bottom edge was cut
  off in your photo and has been filled in."** when `hem_extended` is true.
- A **"Regenerate"** button in the modal calls the endpoint again.
- On error, show the API's `detail` text in the modal in the file's existing
  error style, and keep the modal open.

## Done when
`cd wardrobe/frontend && npm run build` succeeds with no errors.

## Do not
- Do not edit any file other than `Closet.jsx`.
- Do not add a dependency, a new route or a new page.
- Do not change the existing edit/delete behaviour or restyle the closet.
