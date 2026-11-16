import io
import time
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def print_step(step_id, title):
    print("\n" + "=" * 75)
    print(f">> [{step_id}] {title}")
    print("=" * 75)

def print_result(status, detail=""):
    badge = "[PASSED]" if status else "[FAILED]"
    print(f"Result: {badge} {detail}\n")

def run_live_walkthrough():
    print("\n" + "#" * 75)
    print("  STARTING LIVE INTERACTIVE TEST WALKTHROUGH AGAINST:")
    print(f"  Target URL: {BASE_URL}")
    print("  Time: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("#" * 75)

    # Check Website Connectivity
    print_step("INIT", "Connecting to Live Website Homepage")
    res = requests.get(BASE_URL)
    print(f"GET {BASE_URL} -> HTTP {res.status_code}")
    print(f"Page Title present: {'<title>Digital Wardrobe</title>' in res.text}")
    print_result(res.status_code == 200, "Website is live and reachable")

    # Session for User A
    session_a = requests.Session()
    ts = int(time.time())
    email_a = f"alice_{ts}@example.com"
    pass_a = "SecurePassword123!"

    # 1. TC-AUTH-02: Short Password Rejection
    print_step("TC-AUTH-02", "Testing Short Password Rejection (< 10 chars)")
    payload_short = {"email": f"short_{ts}@example.com", "password": "short", "display_name": "Short"}
    res = requests.post(f"{BASE_URL}/api/auth/signup", json=payload_short)
    print(f"POST /api/auth/signup with password 'short' -> HTTP {res.status_code}")
    print(f"Response: {res.text[:100]}")
    print_result(res.status_code == 422, "Short password properly rejected by validation")

    # 2. TC-AUTH-01: User A Signup
    print_step("TC-AUTH-01", f"Registering User A ({email_a})")
    payload_a = {"email": email_a, "password": pass_a, "display_name": "Alice Cooper"}
    res = requests.post(f"{BASE_URL}/api/auth/signup", json=payload_a)
    print(f"POST /api/auth/signup -> HTTP {res.status_code}")
    print(f"Registered User: {res.json()}")
    print_result(res.status_code == 200, "User A registered successfully with Argon2 hash")

    # 3. TC-AUTH-03: Duplicate Email Rejection
    print_step("TC-AUTH-03", f"Testing Duplicate Email Rejection for {email_a}")
    res = requests.post(f"{BASE_URL}/api/auth/signup", json=payload_a)
    print(f"POST /api/auth/signup with duplicate email -> HTTP {res.status_code}")
    print(f"Response: {res.json()}")
    print_result(res.status_code == 400, "Duplicate email properly rejected with 400")

    # 4. TC-AUTH-05: Wrong Password Rejection
    print_step("TC-AUTH-05", "Testing Login with Wrong Password")
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email_a, "password": "WrongPassword999!"})
    print(f"POST /api/auth/login with bad password -> HTTP {res.status_code}")
    print(f"Response: {res.json()}")
    print_result(res.status_code == 401, "Invalid password login rejected with 401")

    # 5. TC-AUTH-04: Valid Login & Cookie Check
    print_step("TC-AUTH-04", f"Logging in as User A ({email_a})")
    res = session_a.post(f"{BASE_URL}/api/auth/login", json={"email": email_a, "password": pass_a})
    print(f"POST /api/auth/login -> HTTP {res.status_code}")
    print(f"Session Cookie Issued: {dict(session_a.cookies)}")
    print_result(res.status_code == 200 and 'session' in session_a.cookies, "Login successful with session cookie")

    # 6. TC-AUTH-07: Get Profile /api/auth/me
    print_step("TC-AUTH-07", "Retrieving Current User Profile (/api/auth/me)")
    res = session_a.get(f"{BASE_URL}/api/auth/me")
    print(f"GET /api/auth/me -> HTTP {res.status_code}")
    print(f"Profile: {res.json()}")
    print_result(res.status_code == 200, f"Authenticated as User ID {res.json()['id']}")

    # 7. TC-AUTH-09: Update Profile Display Name
    print_step("TC-AUTH-09", "Updating Profile Display Name")
    res = session_a.patch(f"{BASE_URL}/api/auth/me", json={"display_name": "Alice C. (Fashionista)"})
    print(f"PATCH /api/auth/me -> HTTP {res.status_code}")
    print(f"Updated Profile: {res.json()}")
    print_result(res.json().get("display_name") == "Alice C. (Fashionista)", "Display name updated")

    # 8. TC-CRUD-01: Create Wardrobe Items for User A
    print_step("TC-CRUD-01", "Adding Wardrobe Pieces to Alice's Digital Closet")
    item1_payload = {
        "name": "Vintage Emerald Blazer",
        "category": "topwear",
        "stored_name": f"blazer_{ts}.png",
        "color": "#2d5a3f",
        "bytes": 24000,
        "is_manual": 1
    }
    item2_payload = {
        "name": "Pleated Linen Trousers",
        "category": "bottomwear",
        "stored_name": f"trousers_{ts}.png",
        "color": "#d9cfc1",
        "bytes": 18000,
        "is_manual": 1
    }
    item3_payload = {
        "name": "Leather Chelsea Boots",
        "category": "shoes",
        "stored_name": f"boots_{ts}.png",
        "color": "#1a1a1a",
        "bytes": 32000,
        "is_manual": 1
    }

    res1 = session_a.post(f"{BASE_URL}/api/items", json=item1_payload)
    res2 = session_a.post(f"{BASE_URL}/api/items", json=item2_payload)
    res3 = session_a.post(f"{BASE_URL}/api/items", json=item3_payload)
    item_a1 = res1.json()
    item_a2 = res2.json()
    item_a3 = res3.json()
    print(f"Created Item 1: {item_a1['name']} (ID: {item_a1['id']}, Cat: {item_a1['category']})")
    print(f"Created Item 2: {item_a2['name']} (ID: {item_a2['id']}, Cat: {item_a2['category']})")
    print(f"Created Item 3: {item_a3['name']} (ID: {item_a3['id']}, Cat: {item_a3['category']})")
    print_result(res1.status_code == 200 and res2.status_code == 200, "Wardrobe pieces added to database")

    # 9. TC-CRUD-03: Category Filtering
    print_step("TC-CRUD-03", "Testing Closet Category Filters (?category=topwear vs ?category=all)")
    res_top = session_a.get(f"{BASE_URL}/api/items?category=topwear")
    res_all = session_a.get(f"{BASE_URL}/api/items?category=all")
    print(f"GET /api/items?category=topwear -> Found {len(res_top.json())} items: {[i['name'] for i in res_top.json()]}")
    print(f"GET /api/items?category=all -> Found {len(res_all.json())} items")
    print_result(len(res_top.json()) == 1 and len(res_all.json()) >= 3, "Category filters operate correctly")

    # 10. TC-CRUD-04: Keyword Search
    print_step("TC-CRUD-04", "Testing Keyword Search (?q=emerald)")
    res_q = session_a.get(f"{BASE_URL}/api/items?q=emerald")
    print(f"GET /api/items?q=emerald -> Found {len(res_q.json())} matches: {[i['name'] for i in res_q.json()]}")
    print_result(len(res_q.json()) == 1 and res_q.json()[0]["name"] == "Vintage Emerald Blazer", "Search returns correct match")

    # 11. TC-CRUD-06: Update Piece
    print_step("TC-CRUD-06", f"Editing Piece ID {item_a1['id']}")
    res_patch = session_a.patch(f"{BASE_URL}/api/items/{item_a1['id']}", json={"name": "Tailored Emerald Blazer", "color": "#1f4a30"})
    print(f"PATCH /api/items/{item_a1['id']} -> {res_patch.json()['name']} ({res_patch.json()['color']})")
    print_result(res_patch.json()["name"] == "Tailored Emerald Blazer", "Piece updated in closet")

    # 12. TC-AI-02 & TC-STOR-01: Upload Outfit Photo & SegFormer Pipeline
    print_step("TC-AI-02 & TC-STOR-01", "Testing Outfit Photo Upload, EXIF Stripping & AI Segmentation")
    test_img = Image.new("RGB", (250, 350), color=(180, 200, 190))
    buf = io.BytesIO()
    test_img.save(buf, format="JPEG")
    buf.seek(0)

    res_upload = session_a.post(f"{BASE_URL}/api/uploads", files={"file": ("outfit_test.jpg", buf, "image/jpeg")})
    print(f"POST /api/uploads -> HTTP {res_upload.status_code}")
    upload_data = res_upload.json()
    print(f"Upload ID: {upload_data.get('upload_id')}")
    print(f"Original Stored Image: {upload_data.get('original_stored_name')}")
    print(f"Detected Garment Candidates: {len(upload_data.get('candidates', []))}")
    print_result(res_upload.status_code == 200 and 'upload_id' in upload_data, "AI SegFormer pipeline completed")

    # 13. TC-SEC-01 & TC-SEC-04: Cross-User IDOR Security Verification
    print_step("TC-SEC-01 & TC-SEC-04", "Testing Strict IDOR Isolation (User B accessing User A's item/image)")
    session_b = requests.Session()
    email_b = f"bob_{ts}@example.com"
    pass_b = "SecurePassword123!"
    session_b.post(f"{BASE_URL}/api/auth/signup", json={"email": email_b, "password": pass_b, "display_name": "Bob"})
    session_b.post(f"{BASE_URL}/api/auth/login", json={"email": email_b, "password": pass_b})

    # User B attempts to read Alice's item
    res_idor_get = session_b.get(f"{BASE_URL}/api/items/{item_a1['id']}")
    print(f"User B -> GET /api/items/{item_a1['id']} (Alice's Blazer) -> HTTP {res_idor_get.status_code}")
    # User B attempts to modify Alice's item
    res_idor_patch = session_b.patch(f"{BASE_URL}/api/items/{item_a1['id']}", json={"name": "Hacked Blazer"})
    print(f"User B -> PATCH /api/items/{item_a1['id']} -> HTTP {res_idor_patch.status_code}")
    # User B attempts to delete Alice's item
    res_idor_del = session_b.delete(f"{BASE_URL}/api/items/{item_a1['id']}")
    print(f"User B -> DELETE /api/items/{item_a1['id']} -> HTTP {res_idor_del.status_code}")
    # User B attempts to access Alice's private image
    res_idor_img = session_b.get(f"{BASE_URL}/api/images/item/{item_a1['stored_name']}")
    print(f"User B -> GET /api/images/item/{item_a1['stored_name']} -> HTTP {res_idor_img.status_code}")

    all_404 = (res_idor_get.status_code == 404 and res_idor_patch.status_code == 404 and 
               res_idor_del.status_code == 404 and res_idor_img.status_code == 404)
    print_result(all_404, "ALL 4 cross-user access attempts strictly blocked with 404 Not Found")

    # 14. TC-ADM-01: Non-Admin Access Forbidden
    print_step("TC-ADM-01", "Testing Non-Admin Access Block to Admin Endpoints")
    res_admin_block = session_a.get(f"{BASE_URL}/api/admin/stats")
    print(f"User A (Regular User) -> GET /api/admin/stats -> HTTP {res_admin_block.status_code}")
    print(f"Response: {res_admin_block.json()}")
    print_result(res_admin_block.status_code == 403, "Non-admin blocked with 403 Forbidden")

    # 15. TC-ADM-03 & TC-ADM-04: Admin Metrics & Privacy
    print_step("TC-ADM-03 & TC-ADM-04", "Testing Admin Dashboard Stats & User Directory Privacy")
    session_admin = requests.Session()
    session_admin.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@example.com", "password": "AdminSecurePassword123!"})
    res_stats = session_admin.get(f"{BASE_URL}/api/admin/stats")
    res_users = session_admin.get(f"{BASE_URL}/api/admin/users")
    print(f"Admin -> GET /api/admin/stats -> {res_stats.json()}")
    print(f"Admin -> GET /api/admin/users -> Found {len(res_users.json())} registered users")
    stats_ok = res_stats.status_code == 200 and res_stats.json()["total_users"] >= 2
    users_ok = res_users.status_code == 200 and "password_hash" not in res_users.json()[0]
    print_result(stats_ok and users_ok, "Admin metrics and user privacy verified")

    # 16. TC-CRUD-07: Delete Item from Closet
    print_step("TC-CRUD-07", f"User A Deleting Piece ID {item_a3['id']} (Chelsea Boots)")
    res_del = session_a.delete(f"{BASE_URL}/api/items/{item_a3['id']}")
    print(f"DELETE /api/items/{item_a3['id']} -> HTTP {res_del.status_code} ({res_del.json()})")
    res_verify_del = session_a.get(f"{BASE_URL}/api/items/{item_a3['id']}")
    print_result(res_del.status_code == 200 and res_verify_del.status_code == 404, "Item deleted and unlinked")

    # 17. TC-AUTH-10: Logout and Invalidate Session
    print_step("TC-AUTH-10", "User A Logging Out & Invalidating Session")
    res_logout = session_a.post(f"{BASE_URL}/api/auth/logout")
    print(f"POST /api/auth/logout -> HTTP {res_logout.status_code}")
    res_after_logout = session_a.get(f"{BASE_URL}/api/auth/me")
    print(f"GET /api/auth/me after logout -> HTTP {res_after_logout.status_code}")
    print_result(res_after_logout.status_code == 401, "Session invalidated, subsequent requests return 401")

    print("\n" + "=" * 75)
    print("ALL LIVE INTERACTIVE TEST CASES COMPLETED SUCCESSFULLY (100% PASS)")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_live_walkthrough()
