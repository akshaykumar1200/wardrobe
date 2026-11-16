# Digital Wardrobe Test Suite (Q2)

Comprehensive automated test suite covering authentication, security/IDOR isolation, item management, EXIF metadata stripping, admin metrics, and AI segmentation.

---

## 📁 Test Suite Structure

| Test File | Focus Area | Key Assertions Verified |
| :--- | :--- | :--- |
| **`test_auth.py`** | Authentication & Sessions | - User signup & Argon2 password hashing<br>- Minimum 10-char password validation<br>- Duplicate email rejection (400)<br>- Login & HttpOnly session cookie creation<br>- Password mismatch rejection (401)<br>- User profile retrieval (`/api/auth/me`) & PATCH update<br>- Logout session table invalidation |
| **`test_idor_security.py`** | IDOR Isolation & Security | - Cross-user `GET /api/items/{id}` returns **404 Not Found**<br>- Cross-user `PATCH /api/items/{id}` returns **404 Not Found**<br>- Cross-user `DELETE /api/items/{id}` returns **404 Not Found**<br>- Cross-user image access returns **404 Not Found**<br>- Unauthenticated calls return **401 Unauthorized**<br>- Path traversal attacks blocked |
| **`test_items_crud.py`** | Wardrobe Pieces CRUD | - Item creation (name, category, stored image, color hex)<br>- Category filtering (`topwear`, `bottomwear`, `shoes`, `accessories`, `other`)<br>- Substring search (`?q=...`)<br>- Item update & recategorization<br>- Item deletion (DB deletion + storage file unlinking) |
| **`test_storage_exif.py`** | Storage & Privacy | - **EXIF / GPS metadata stripping** from saved images on disk<br>- Content-Type filtering (rejects non-images with 415)<br>- File size limits (rejects >10MB with 413)<br>- Corrupt image payload rejection (400)<br>- Decompression bomb protection (>50M pixels rejected) |
| **`test_admin.py`** | RBAC & Admin Metrics | - Regular user blocked from admin endpoints (403)<br>- Admin stats aggregation (user count, items, uploads, bytes)<br>- User directory privacy (zero leaked password hashes or image URLs) |
| **`test_ai_segmentation.py`** | AI Segmentation Pipeline | - Dominant color hex calculation<br>- `/api/uploads` multipart upload processing & candidate generation |

---

## 🚀 How to Run the Tests

### Option 1: Run All Tests with the Runner Script
```powershell
cd C:\Users\Lenovo\Desktop\fasion
.\wardrobe\venv\Scripts\python.exe q2\run_all_tests.py
```

### Option 2: Run directly with pytest
```powershell
cd C:\Users\Lenovo\Desktop\fasion
$env:PYTHONPATH=".\wardrobe"
.\wardrobe\venv\Scripts\pytest.exe -v q2/
```
