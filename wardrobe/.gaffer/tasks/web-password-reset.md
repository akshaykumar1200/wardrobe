---
id: web-password-reset
files: [wardrobe/backend/routers/admin.py, wardrobe/backend/routers/auth_routes.py, wardrobe/backend/schemas.py, wardrobe/frontend/src/pages/Admin.jsx, wardrobe/frontend/src/pages/Login.jsx, wardrobe/frontend/src/pages/ChangePassword.jsx, wardrobe/frontend/src/App.jsx, wardrobe/frontend/src/components/Navbar.jsx, wardrobe/tests/test_password_reset.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
This app has no way to recover a forgotten password and no way to change a
password at all. Add both, for the **website only**. Do not touch
`../android_app/`.

There is **no email infrastructure** in this project and none is to be added:
no SMTP, no mail dependency, no reset-token table, no expiring links. The
admin resets a forgotten password by hand and reads the new one out to the
person. This is a three-account family app; that is the whole requirement.

Read `backend/routers/auth_routes.py`, `backend/routers/admin.py`,
`backend/auth.py` and `backend/schemas.py` first.

## 1. `POST /api/admin/users/{user_id}/reset-password`

In `backend/routers/admin.py`, guarded by the existing
`current_admin` dependency like the other two routes in that file.

- Generate the password with `secrets.token_urlsafe(12)`. Do not write your
  own alphabet or use `random`.
- Hash it with `hash_password` from `backend.auth`. Never store plaintext.
- **Delete every row in `sessions` for that user.** A forgotten password may
  mean a shared or stolen one, so every existing login for that account must
  stop working. `Session.user_id` is the column; import `Session` from
  `backend.models`.
- Return `{"password": "<the new one>"}`. This is the only time it is ever
  readable, so say that in a docstring.
- **Never `print` or log the password**, and do not put it in an error
  message. `main.py` prints on bootstrap; do not copy that habit here.
- 404 if no such user.

## 2. `POST /api/auth/change-password`

In `backend/routers/auth_routes.py`, for the signed-in user
(`current_user`), so a person handed a generated password can set their own.

- Body: `current_password` and `new_password`. Add a schema beside
  `SignupRequest` in `schemas.py` with the **same `min_length=10`** on
  `new_password` that `SignupRequest.password` already has. Do not invent a
  different rule.
- Verify `current_password` with `verify_password` and return **400** if it
  is wrong. Knowing the current password is what makes this safe.
- Reject a `new_password` equal to the current one.
- Delete that user's **other** sessions, keeping the token the request came
  in on, so changing your password signs out your other devices but not the
  tab you are using. The current token is available from the
  `session_token` dependency in `backend/auth.py`.

## 3. `Login.jsx` — "Forgot password?"

One line under the Sign In button, in the same style as the existing
"Don't have an account?" line below it. It is **not** a link to a page: there
is no self-service reset. It says the admin can reset it, e.g. a small
expandable line or static text reading "Forgot your password? Ask the
wardrobe admin to reset it for you." Keep it to a few lines of JSX.

## 4. `Admin.jsx` — a reset button per user

The user table is already there and already has each user's `id`.

- A "Reset password" button in each row, matching the buttons already in the
  file. No new colours.
- Clicking it asks for confirmation first (it kills that user's logins).
- On success, show the returned password **in the page, once**, with a copy
  button, and make clear in the surrounding text that it will not be shown
  again and must be given to the person now.
- Do not store it in state longer than the panel is open, and do not
  `console.log` it.

## 5. `ChangePassword.jsx` (new) + `App.jsx` + `Navbar.jsx`

- A new page at route `/password`: three fields (current, new, confirm), a
  submit button, and inline error text. Match `Login.jsx` exactly for
  layout, input classes and button style — same card, same palette.
- Reject a mismatch between new and confirm **in the page** before calling
  the API.
- Wire the route in `App.jsx` as a protected route, the same way `/upload`
  is wired.
- Add one link to it in `Navbar.jsx`, in the right-hand group near the
  display name and the logout icon. Do not restyle the navbar.

## 6. `tests/test_password_reset.py` (new)

Follow the fixtures and style of `tests/test_security.py`. Cover:

- a non-admin calling the admin reset endpoint is refused
- after an admin reset, the old password no longer logs in and the returned
  one does
- after an admin reset, a session token that worked before the reset is
  rejected
- change-password with the wrong current password returns 400 and leaves the
  password unchanged
- change-password succeeds and the token used for the request still works

## Done when

`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes: all 36
existing tests plus the new ones, none skipped.

## Do not

- Do not add any dependency, or any email, SMTP or token-link machinery.
- Do not add a reset-token column, table or migration.
- Do not change `backend/crops.py`, `database.py`, `models.py`, or the
  items/outfits/wears/uploads routers.
- Do not touch anything under `../android_app/`.
- Do not change the colour palette or restyle existing screens.
- Do not run `npm run build`; the rebuild is a separate step.
