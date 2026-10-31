---
id: email-case
files: [wardrobe/backend/schemas.py, wardrobe/backend/main.py, wardrobe/tests/test_email_case.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
Email addresses are compared case-sensitively, which is wrong and is already
biting a real account.

A live user is stored as `Akshaypsg30@gmail.com` with a capital A. Every
lookup in `backend/routers/auth_routes.py` is
`db.query(User).filter(User.email == payload.email)`, and on Postgres `==` on
a String column is case-sensitive. So:

- **Login** fails with "wrong password" if the address is typed in a
  different case than it was registered.
- **Forgot password** finds nothing, sends nothing, and still answers "a
  reset link is on its way" — because that endpoint deliberately never
  reveals whether an account exists. The person gets silence.
- **Signup** would happily create a second account differing only by
  capitalisation.

Email addresses are case-insensitive in practice; every mail provider treats
them that way.

Read `backend/schemas.py`, `backend/routers/auth_routes.py` and
`backend/main.py` first.

## 1. Normalise at the schema, not at each query

`backend/schemas.py` has `email` fields on `SignupRequest`, `LoginRequest`
and `ForgotPasswordRequest`. Add a `field_validator` to each that **strips
surrounding whitespace and lowercases** the address.

Do it there, not in the routers. The schema is the one place every request
passes through, so the value is already normalised by the time it reaches
both the `filter(...)` and the `User(email=...)` insert — which means the
read and the write can never disagree. **Do not** edit the three query lines
in `auth_routes.py`; if you find yourself doing that, the normalisation is in
the wrong place.

Follow the existing `field_validator` style already in that file (see
`UserUpdate.sensible_name`).

Leave the output schema's `email` field alone — it reports what is stored.

## 2. `backend/main.py` — the admin bootstrap

Line 53 looks the admin up by `settings.ADMIN_EMAIL` and line 56 creates them
with it. That value comes from `.env` and never passes through a schema, so
it is not normalised. Lowercase and strip it in **both** places, so a
capitalised `ADMIN_EMAIL` cannot create a second admin row that the login
form can then never match.

## 3. `tests/test_email_case.py` (new)

Follow the fixtures and style of `tests/test_password_reset.py`. Cover:

- sign up with a mixed-case address, then **log in with it lowercased** —
  succeeds
- sign up with a mixed-case address, then **log in with it uppercased** —
  succeeds
- signing up again with the same address in a different case is **rejected
  as a duplicate**, not allowed through as a second account
- forgot-password with a different case than registered **finds the user**:
  assert a `PasswordReset` row is created (monkeypatch the mail sender, as
  `test_email_reset.py` does, so nothing is sent)
- an address with leading or trailing spaces is accepted and matches

## Done when

`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes all **47**
existing tests plus the new ones, none skipped.

## Do not

- Do not change the three `User.email ==` comparisons in `auth_routes.py`.
- Do not write a database migration or change existing rows; the live data is
  being corrected separately.
- Do not change `backend/models.py`, the column type, or add a database-level
  collation or index.
- Do not touch `crops.py`, `database.py`, the items/outfits/wears/uploads
  routers, `mailer.py`, or anything under `../android_app/`.
- Do not add a dependency.
