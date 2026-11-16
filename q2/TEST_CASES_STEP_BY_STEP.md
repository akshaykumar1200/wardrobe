# Digital Wardrobe: Comprehensive Test Cases & Step-by-Step Guide

This document accompanies the [`test_cases_report.csv`](file:///C:/Users/Lenovo/Desktop/fasion/q2/test_cases_report.csv) file located in the `q2/` folder. It outlines each of the **34 test cases**, their preconditions, step-by-step execution procedures, expected outcomes, and actual test results.

---

## 📊 Summary of Test Execution

- **Total Test Cases:** 34
- **Passed:** 34 (100%)
- **Failed:** 0 (0%)
- **Test Runner:** `pytest` 9.1.1 + Python 3.11
- **Target Application:** Digital Wardrobe Backend & API (`FastAPI + SQLite + SegFormer + Argon2`)

---

## 1. Authentication & Session Management (`test_auth.py`)

### TC-AUTH-01: User Signup Success
* **Preconditions:** Database initialized.
* **Steps to Follow:**
  1. Prepare JSON payload with `email: "freshuser@example.com"`, `password: "SuperSecretPassword123!"` (≥ 10 characters), and `display_name: "Fresh User"`.
  2. Send `POST /api/auth/signup`.
  3. Inspect HTTP response status code and JSON body.
  4. Query the SQLite `users` table for the email address.
* **Expected Result:** HTTP 200 OK. Response body contains user ID, email, and display name. Database stores an Argon2id hashed password (`$argon2id$...`), never plaintext.
* **Actual Result:** **PASSED** (200 OK, password hash starts with `$argon2id$`).

### TC-AUTH-02: Short Password Rejection (< 10 Characters)
* **Preconditions:** None.
* **Steps to Follow:**
  1. Prepare JSON payload with `email: "shortpass@example.com"` and `password: "short"`.
  2. Send `POST /api/auth/signup`.
* **Expected Result:** HTTP 422 Unprocessable Entity. Request rejected before database insertion.
* **Actual Result:** **PASSED** (422 validation error returned).

### TC-AUTH-03: Duplicate Email Registration Rejection
* **Preconditions:** User `usera@example.com` already registered.
* **Steps to Follow:**
  1. Send `POST /api/auth/signup` using `email: "usera@example.com"` and a valid password.
* **Expected Result:** HTTP 400 Bad Request with detail message `"Email already registered"`.
* **Actual Result:** **PASSED** (400 Bad Request returned).

### TC-AUTH-04: User Login & Session Cookie Issuance
* **Preconditions:** User exists in DB with known password.
* **Steps to Follow:**
  1. Send `POST /api/auth/login` with valid email and password.
  2. Inspect response headers for `Set-Cookie`.
* **Expected Result:** HTTP 200 OK. Response contains `{"ok": true}` and a secure `session` cookie with `HttpOnly=True` and `SameSite=Lax`.
* **Actual Result:** **PASSED** (200 OK, `session` cookie set).

### TC-AUTH-05: Invalid Password Login Rejection
* **Preconditions:** User exists in DB.
* **Steps to Follow:**
  1. Send `POST /api/auth/login` with correct email and incorrect password `"WrongPassword999!"`.
* **Expected Result:** HTTP 401 Unauthorized with detail `"Invalid email or password"`.
* **Actual Result:** **PASSED** (401 Unauthorized returned).

### TC-AUTH-06: Non-Existent User Login Rejection
* **Preconditions:** User does not exist.
* **Steps to Follow:**
  1. Send `POST /api/auth/login` with unregistered email `nobody@example.com`.
* **Expected Result:** HTTP 401 Unauthorized.
* **Actual Result:** **PASSED** (401 Unauthorized returned).

### TC-AUTH-07: Get Authenticated User Profile (`/api/auth/me`)
* **Preconditions:** User is logged in with an active session cookie.
* **Steps to Follow:**
  1. Send `GET /api/auth/me` including the `session` cookie.
* **Expected Result:** HTTP 200 OK returning the logged-in user's profile (`id`, `email`, `display_name`, `is_admin`).
* **Actual Result:** **PASSED** (200 OK, user profile matched).

### TC-AUTH-08: Unauthenticated Profile Access Rejection
* **Preconditions:** No session cookie provided.
* **Steps to Follow:**
  1. Send `GET /api/auth/me` without any cookies.
* **Expected Result:** HTTP 401 Unauthorized.
* **Actual Result:** **PASSED** (401 Unauthorized returned).

### TC-AUTH-09: Update Profile Display Name
* **Preconditions:** User is logged in.
* **Steps to Follow:**
  1. Send `PATCH /api/auth/me` with `{"display_name": "Updated Alpha Name"}`.
  2. Query database `users` table to verify persistence.
* **Expected Result:** HTTP 200 OK. Display name is updated in the database and returned in response.
* **Actual Result:** **PASSED** (200 OK, updated display name persisted).

### TC-AUTH-10: Logout & Session Invalidation
* **Preconditions:** User is logged in.
* **Steps to Follow:**
  1. Send `POST /api/auth/logout`.
  2. Query `sessions` table in SQLite for the session token.
  3. Attempt subsequent `GET /api/auth/me` with the previous cookie.
* **Expected Result:** HTTP 200 OK. Session row is deleted from database; subsequent request returns 401.
* **Actual Result:** **PASSED** (Session row destroyed; subsequent call returned 401).

---

## 2. Security & IDOR Isolation (`test_idor_security.py`)

### TC-SEC-01: Cross-User Item Read Blocked (IDOR)
* **Preconditions:** User A owns Item #1. User B is authenticated with their own session.
* **Steps to Follow:**
  1. User B sends `GET /api/items/{User_A_item_id}`.
* **Expected Result:** HTTP **404 Not Found** (Strictly 404, never 403, to prevent existence discovery).
* **Actual Result:** **PASSED** (404 Not Found returned).

### TC-SEC-02: Cross-User Item Update Blocked
* **Preconditions:** User A owns Item #1. User B is authenticated.
* **Steps to Follow:**
  1. User B sends `PATCH /api/items/{User_A_item_id}` with `{"name": "Hacked Name"}`.
  2. Query database for User A's item.
* **Expected Result:** HTTP 404 Not Found. Item in database remains unchanged.
* **Actual Result:** **PASSED** (404 Not Found returned; DB record untouched).

### TC-SEC-03: Cross-User Item Delete Blocked
* **Preconditions:** User A owns Item #1. User B is authenticated.
* **Steps to Follow:**
  1. User B sends `DELETE /api/items/{User_A_item_id}`.
  2. Query database to ensure item still exists.
* **Expected Result:** HTTP 404 Not Found. Item remains intact in database.
* **Actual Result:** **PASSED** (404 Not Found returned; item preserved).

### TC-SEC-04: Cross-User Garment Image Access Blocked
* **Preconditions:** User A owns garment cutout image `user_a_test_shirt.png`. User B is authenticated.
* **Steps to Follow:**
  1. User B sends `GET /api/images/item/user_a_test_shirt.png`.
* **Expected Result:** HTTP 404 Not Found.
* **Actual Result:** **PASSED** (404 Not Found returned; private image unexposed).

### TC-SEC-05: Anonymous Item Access Blocked
* **Preconditions:** Unauthenticated client.
* **Steps to Follow:**
  1. Send `GET /api/items`, `GET /api/items/1`, and `GET /api/images/item/test.png` without cookies.
* **Expected Result:** HTTP 401 Unauthorized for all endpoints.
* **Actual Result:** **PASSED** (401 returned across all endpoints).

### TC-SEC-06: Path Traversal Attack Blocked
* **Preconditions:** User is authenticated.
* **Steps to Follow:**
  1. Send `GET /api/images/item/../../database.py`.
* **Expected Result:** Path traversal blocked via `is_relative_to` check returning 400 Bad Request or 404.
* **Actual Result:** **PASSED** (Path traversal blocked).

---

## 3. Wardrobe Item CRUD Operations (`test_items_crud.py`)

### TC-CRUD-01: Create Wardrobe Piece
* **Preconditions:** User is logged in.
* **Steps to Follow:**
  1. Send `POST /api/items` with piece metadata (`name: "Vintage Denim Jacket"`, `category: "topwear"`, `stored_name: "denim_123.png"`, `color: "#2c4c64"`).
* **Expected Result:** HTTP 200 OK. Item created in database with `user_id == current_user.id`.
* **Actual Result:** **PASSED** (200 OK, item created).

### TC-CRUD-02: List Empty Closet
* **Preconditions:** User has no items saved.
* **Steps to Follow:**
  1. Send `GET /api/items`.
* **Expected Result:** HTTP 200 OK with empty array `[]`.
* **Actual Result:** **PASSED** (200 OK, empty list returned).

### TC-CRUD-03: Filter Items by Category
* **Preconditions:** User has topwear, bottomwear, and shoes saved in their closet.
* **Steps to Follow:**
  1. Send `GET /api/items?category=topwear`.
  2. Send `GET /api/items?category=all`.
* **Expected Result:** `category=topwear` returns only tops. `category=all` returns all pieces.
* **Actual Result:** **PASSED** (Correct items returned for each filter).

### TC-CRUD-04: Search Items by Keyword
* **Preconditions:** User has "Oversized Linen Shirt" and "Silk Scarf".
* **Steps to Follow:**
  1. Send `GET /api/items?q=linen`.
* **Expected Result:** Case-insensitive substring match returning only "Oversized Linen Shirt".
* **Actual Result:** **PASSED** (Matching item returned).

### TC-CRUD-05: Retrieve Specific Item
* **Preconditions:** User owns item.
* **Steps to Follow:**
  1. Send `GET /api/items/{item_id}`.
* **Expected Result:** HTTP 200 OK with item details.
* **Actual Result:** **PASSED** (200 OK returned).

### TC-CRUD-06: Update Piece Name and Category
* **Preconditions:** User owns item.
* **Steps to Follow:**
  1. Send `PATCH /api/items/{item_id}` with `{"name": "Wool Overcoat", "category": "other"}`.
* **Expected Result:** HTTP 200 OK with updated attributes.
* **Actual Result:** **PASSED** (200 OK, updated fields saved).

### TC-CRUD-07: Delete Item & Physical File Cleanup
* **Preconditions:** User owns item with corresponding file in `storage/users/{user_id}/items/`.
* **Steps to Follow:**
  1. Send `DELETE /api/items/{item_id}`.
  2. Inspect database and verify file system.
* **Expected Result:** HTTP 200 OK. Database row deleted and physical file on disk unlinked.
* **Actual Result:** **PASSED** (DB record deleted and disk file unlinked).

---

## 4. Storage Validation & EXIF Stripping (`test_storage_exif.py`)

### TC-STOR-01: EXIF & GPS Location Metadata Stripping
* **Preconditions:** JPEG generated with embedded EXIF tags (Tag 270 ImageDescription, GPS data).
* **Steps to Follow:**
  1. Run `validate_and_store_original()` with the EXIF JPEG.
  2. Read the saved JPEG file from disk and inspect its EXIF tags via PIL.
* **Expected Result:** Cleaned image on disk contains zero EXIF metadata tags.
* **Actual Result:** **PASSED** (0 EXIF tags on disk).

### TC-STOR-02: Non-Image Content Type Rejection
* **Preconditions:** None.
* **Steps to Follow:**
  1. Send upload payload with `Content-Type: application/pdf`.
* **Expected Result:** HTTP 415 Unsupported Media Type.
* **Actual Result:** **PASSED** (415 error raised).

### TC-STOR-03: Max Upload Size Enforcement (> 10MB)
* **Preconditions:** None.
* **Steps to Follow:**
  1. Send image payload of 11 MB.
* **Expected Result:** HTTP 413 Payload Too Large.
* **Actual Result:** **PASSED** (413 error raised).

### TC-STOR-04: Corrupted Image Payload Rejection
* **Preconditions:** None.
* **Steps to Follow:**
  1. Send corrupted byte sequence claiming to be JPEG.
* **Expected Result:** HTTP 400 Bad Request upon PIL decode verification failure.
* **Actual Result:** **PASSED** (400 error raised).

### TC-STOR-05: Decompression Bomb Protection
* **Preconditions:** None.
* **Steps to Follow:**
  1. Send image with dimensions 10,000 x 6,000 pixels (60 million pixels > 50M limit).
* **Expected Result:** HTTP 400 Bad Request with `"resolution is too large"`.
* **Actual Result:** **PASSED** (Decompression bomb rejected with 400).

---

## 5. Admin Dashboard & RBAC (`test_admin.py`)

### TC-ADM-01: Non-Admin Stats Access Forbidden
* **Preconditions:** Regular user logged in.
* **Steps to Follow:**
  1. Send `GET /api/admin/stats`.
* **Expected Result:** HTTP 403 Forbidden with `"Admin access required"`.
* **Actual Result:** **PASSED** (403 Forbidden returned).

### TC-ADM-02: Non-Admin User List Access Forbidden
* **Preconditions:** Regular user logged in.
* **Steps to Follow:**
  1. Send `GET /api/admin/users`.
* **Expected Result:** HTTP 403 Forbidden.
* **Actual Result:** **PASSED** (403 Forbidden returned).

### TC-ADM-03: Admin System Metrics Aggregation
* **Preconditions:** Admin user logged in.
* **Steps to Follow:**
  1. Send `GET /api/admin/stats`.
* **Expected Result:** HTTP 200 OK with `total_users`, `total_items`, `total_uploads`, `storage_bytes`, and category breakdown.
* **Actual Result:** **PASSED** (200 OK with accurate system counts).

### TC-ADM-04: User Directory Privacy Protection
* **Preconditions:** Admin user logged in.
* **Steps to Follow:**
  1. Send `GET /api/admin/users`.
  2. Inspect all user records in response.
* **Expected Result:** User metadata is provided (email, role, item count, upload count) without leaking passwords, password hashes, or private image URLs.
* **Actual Result:** **PASSED** (No password hashes or image URLs exposed).

---

## 6. AI Segmentation Pipeline (`test_ai_segmentation.py`)

### TC-AI-01: Dominant Color Extraction
* **Preconditions:** RGB array filled with sage green `(125, 140, 113)`.
* **Steps to Follow:**
  1. Execute `_dominant_color()` helper.
* **Expected Result:** Exact hex color string `"#7d8c71"`.
* **Actual Result:** **PASSED** (Hex `#7d8c71` returned).

### TC-AI-02: Outfit Segmentation Pipeline & Candidate Generation
* **Preconditions:** User is authenticated.
* **Steps to Follow:**
  1. Send `POST /api/uploads` with outfit JPEG.
* **Expected Result:** HTTP 200 OK with `upload_id`, `original_stored_name`, and a list of detected garment candidates.
* **Actual Result:** **PASSED** (200 OK, candidate list generated).
