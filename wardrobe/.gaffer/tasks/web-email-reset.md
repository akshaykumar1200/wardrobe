---
id: web-email-reset
files: [wardrobe/backend/models.py, wardrobe/backend/config.py, wardrobe/backend/mailer.py, wardrobe/backend/routers/auth_routes.py, wardrobe/backend/schemas.py, wardrobe/frontend/src/pages/ForgotPassword.jsx, wardrobe/frontend/src/pages/ResetPassword.jsx, wardrobe/frontend/src/pages/Login.jsx, wardrobe/frontend/src/App.jsx, wardrobe/tests/test_email_reset.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
Add a self-service "forgot password" flow that emails a reset link. The
admin-reset flow added in `web-password-reset` **stays exactly as it is** —
this is an addition, not a replacement.

Mail goes out through **Gmail SMTP using Python's standard library**
(`smtplib` + `email.message.EmailMessage`). Add **no** mail dependency and no
third-party mail SDK.

Read `backend/routers/auth_routes.py`, `backend/auth.py`, `backend/models.py`
and `backend/config.py` first.

## 1. `backend/models.py` — one new table

```
class PasswordReset(Base):
    __tablename__ = "password_resets"
```

Columns: `token_hash` (String, primary key), `user_id` (FK to `users.id`,
`ondelete="CASCADE"`, indexed), `expires_at` (DateTime), `used_at` (DateTime,
nullable), `created_at` (DateTime, default `datetime.utcnow`).

- **Store only a SHA-256 hash of the token, never the token itself.** A
  database leak must not hand over live account keys. Use `hashlib.sha256`,
  not `hash_password` — the token is already high-entropy random, and argon2
  salts each hash so it could not be looked up by value.
- Add the matching `relationship`/`back_populates` on `User` with
  `cascade="all, delete-orphan"`, the way `sessions` already does it.
- A brand new table is created by the existing `create_all`; **do not write a
  migration** and do not touch any other model.

## 2. `backend/config.py` — SMTP settings

Add to `Settings`, following the style already there:

- `SMTP_HOST: str = "smtp.gmail.com"`
- `SMTP_PORT: int = 587`
- `SMTP_USER: str = ""`
- `SMTP_PASSWORD: str = ""`
- `SMTP_FROM: str = ""` — falls back to `SMTP_USER` when empty
- `RESET_TOKEN_MINUTES: int = 30`

Do not add a default password or a real address. `PUBLIC_ORIGIN` already
exists; reuse it for the link and do not add another origin setting.

## 3. `backend/mailer.py` (new, small)

One function, e.g. `send_reset_email(to_email: str, reset_url: str) -> None`.

- STARTTLS on `SMTP_PORT`, then login with `SMTP_USER` / `SMTP_PASSWORD`.
- Plain-text body with the link and a line saying it expires in
  `RESET_TOKEN_MINUTES` minutes and can be used once.
- **If `SMTP_USER` or `SMTP_PASSWORD` is empty, log a clear warning and
  return without raising.** A missing app password must not turn into a 500
  for the person using the form.
- Catch `smtplib.SMTPException` and `OSError`, log that sending failed, and
  return. The caller must not leak mail trouble to the browser.
- **Never log the token, the reset URL, or the SMTP password.** Log the
  recipient address at most.

## 4. `POST /api/auth/forgot-password`

In `auth_routes.py`. Body: `email`.

- **Always return the same 200 response**, whether or not that address has an
  account, and never say which it was. Anything else turns this form into a
  way to discover who has an account.
- **Rate limit it with the existing `limiter` from `backend.auth`: 5/hour.**
  It is unauthenticated and it sends mail, so without a limit it is a way to
  send spam from the configured Gmail account. Follow how
  `outfits.py:/recommendations` applies `@limiter.limit`, including the
  `request: Request` parameter that slowapi requires.
- On a real account: generate `secrets.token_urlsafe(32)`, store its sha256
  with `expires_at = utcnow() + RESET_TOKEN_MINUTES`, and
  **delete that user's earlier unused reset rows** so only the newest link
  works.
- Build the link as `{settings.PUBLIC_ORIGIN}/reset?token={token}`.
- Send via **FastAPI `BackgroundTasks`**, so a slow Gmail handshake does not
  hold the response open. Do not add a thread, a queue or a scheduler.
- Inactive accounts (`is_active == 0`) get no email, but the response is the
  same as every other case.

## 5. `POST /api/auth/reset-password`

Body: `token` and `new_password`. Add the schema beside the existing ones in
`schemas.py` with the **same `min_length=10`** as `SignupRequest.password`.

- Look the row up by the sha256 of the presented token.
- Reject with **400** when there is no such row, when `used_at` is set, or
  when `expires_at` has passed. Use one identical message for all three; do
  not tell the caller which it was.
- On success: set the new password with `hash_password`, set `used_at`,
  **delete every row in `sessions` for that user**, and delete that user's
  other unused reset rows. A password reset must end all existing logins.
- Compare times consistently with how `expires_at` is written — check
  whether the codebase stores naive UTC and match it. A mismatch here makes
  every token look expired or never expire.

## 6. Frontend

- `ForgotPassword.jsx` (new), route `/forgot`: one email field. After submit,
  always show the same neutral confirmation, e.g. "If that address has an
  account, a reset link is on its way." Never reveal whether it existed.
- `ResetPassword.jsx` (new), route `/reset`: read `token` from the query
  string with `useSearchParams` from `react-router-dom`. Two fields, new and
  confirm; check they match in the page before calling the API. On success,
  send the person to `/login`. If the token is missing from the URL, say the
  link is invalid rather than posting an empty token.
- Both pages must match `Login.jsx` exactly: same card, same input classes,
  same button, same palette. Do not restyle anything.
- `Login.jsx`: the current line tells people to ask the admin. Make it a real
  link to `/forgot` reading "Forgot your password?", and keep a shorter
  mention that an admin can also reset it.
- `App.jsx`: wire `/forgot` and `/reset` as **public** routes, like `/login`
  and `/signup`. A locked-out person is not signed in, so these must not sit
  behind the auth guard.

## 7. `tests/test_email_reset.py` (new)

Follow the fixtures and style of `tests/test_password_reset.py`.
**Monkeypatch the send function so no real mail is ever sent**, and assert on
what it was called with.

Cover:
- forgot-password for an unknown address returns the same status and body as
  for a known one, and sends nothing
- the emailed link contains a token that then resets the password
- the token is single-use: the second attempt returns 400
- an expired token returns 400 and leaves the password unchanged
- after a successful reset, a session token that worked before is rejected
- requesting a second link invalidates the first one
- the stored `token_hash` is not the raw token

## Done when

`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes: all 41
existing tests plus the new ones, none skipped.

## Do not

- Do not add any dependency; `smtplib` is in the standard library.
- Do not change `backend/crops.py`, `database.py`, the items/outfits/wears/
  uploads routers, or the admin reset endpoint added in `web-password-reset`.
- Do not touch anything under `../android_app/`.
- Do not put a real email address, password or app password in any file.
- Do not write a database migration.
- Do not run `npm run build`; the rebuild is a separate step.
