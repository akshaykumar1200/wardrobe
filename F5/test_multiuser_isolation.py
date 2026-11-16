import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_isolation():
    print("=" * 65)
    print("  TESTING MULTI-USER AUTHENTICATION & DATA ISOLATION")
    print("=" * 65)

    # 1. Register User Alex
    print("\n>> [STEP 1] Registering User 'alex'...")
    res_alex = requests.post(f"{BASE_URL}/api/auth/register", json={"username": "alex", "password": "password_alex_123"})
    if res_alex.status_code == 400 and "already exists" in res_alex.text:
        # Login if already exists
        res_alex = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "alex", "password": "password_alex_123"})
    
    assert res_alex.status_code == 200, f"Alex auth failed: {res_alex.text}"
    token_alex = res_alex.json()["token"]
    headers_alex = {"Authorization": f"Bearer {token_alex}"}
    print(f"   Alex authenticated successfully! Token: {token_alex[:8]}...")

    # 2. Register User Sarah
    print("\n>> [STEP 2] Registering User 'sarah' (Simulating second device/user)...")
    res_sarah = requests.post(f"{BASE_URL}/api/auth/register", json={"username": "sarah", "password": "password_sarah_123"})
    if res_sarah.status_code == 400 and "already exists" in res_sarah.text:
        # Login if already exists
        res_sarah = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "sarah", "password": "password_sarah_123"})

    assert res_sarah.status_code == 200, f"Sarah auth failed: {res_sarah.text}"
    token_sarah = res_sarah.json()["token"]
    headers_sarah = {"Authorization": f"Bearer {token_sarah}"}
    print(f"   Sarah authenticated successfully! Token: {token_sarah[:8]}...")

    # 3. Alex adds a Green Tee
    print("\n>> [STEP 3] Alex saves 'Vintage Green Tee' to his private wardrobe...")
    item_alex_res = requests.post(
        f"{BASE_URL}/api/items",
        headers=headers_alex,
        json={
            "category": "upper",
            "label": "Alex's Vintage Green Tee",
            "path": "/storage/items/top_green_vintage.png",
            "color": "#2c524a",
            "color_name": "pine",
            "colors": [{"hex": "#2c524a", "name": "pine", "share": 1.0}],
            "pattern": "graphic",
            "scale": "bold",
            "pixels": 46681,
            "confidence": 0.98
        }
    )
    item_alex_id = item_alex_res.json()["id"]
    print(f"   Alex saved item ID: {item_alex_id}")

    # 4. Sarah adds Puma Sneakers
    print("\n>> [STEP 4] Sarah saves 'Puma RS Sneakers' to her private wardrobe...")
    item_sarah_res = requests.post(
        f"{BASE_URL}/api/items",
        headers=headers_sarah,
        json={
            "category": "footwear",
            "label": "Sarah's Puma RS Sneakers",
            "path": "/storage/items/shoes_puma_rs_grey.png",
            "color": "#7c7a7b",
            "color_name": "grey",
            "colors": [{"hex": "#7c7a7b", "name": "grey", "share": 1.0}],
            "pattern": "solid",
            "scale": "none",
            "pixels": 812841,
            "confidence": 0.88
        }
    )
    item_sarah_id = item_sarah_res.json()["id"]
    print(f"   Sarah saved item ID: {item_sarah_id}")

    # 5. Verify Isolation: Alex's wardrobe should NOT contain Sarah's Puma Sneakers
    print("\n>> [STEP 5] Verifying Data Isolation...")
    alex_items = requests.get(f"{BASE_URL}/api/items", headers=headers_alex).json()
    sarah_items = requests.get(f"{BASE_URL}/api/items", headers=headers_sarah).json()

    alex_labels = [i["label"] for i in alex_items]
    sarah_labels = [i["label"] for i in sarah_items]

    print(f"   Alex's Wardrobe Items: {alex_labels}")
    print(f"   Sarah's Wardrobe Items: {sarah_labels}")

    assert "Alex's Vintage Green Tee" in alex_labels
    assert "Sarah's Puma RS Sneakers" not in alex_labels, "LEAK DETECTED: Alex can see Sarah's sneakers!"

    assert "Sarah's Puma RS Sneakers" in sarah_labels
    assert "Alex's Vintage Green Tee" not in sarah_labels, "LEAK DETECTED: Sarah can see Alex's tee!"
    print("   [OK] PASS: Data isolation verified! Users only see their own wardrobe.")

    # 6. Verify Unauthorized Deletion Protection
    print("\n>> [STEP 6] Testing Security: Alex tries to delete Sarah's item...")
    del_attack = requests.delete(f"{BASE_URL}/api/items/{item_sarah_id}", headers=headers_alex)
    print(f"   Delete attack status code: {del_attack.status_code} ({del_attack.text})")
    assert del_attack.status_code == 404, "SECURITY ERROR: Alex was able to delete Sarah's item!"
    print("   [OK] PASS: Security check passed! Cross-user item deletion is strictly blocked.")

    # 7. Cross-Device Simulation
    print("\n>> [STEP 7] Simulating Cross-Device Login for Alex...")
    alex_device_2_login = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "alex", "password": "password_alex_123"})
    token_device_2 = alex_device_2_login.json()["token"]
    alex_device_2_items = requests.get(f"{BASE_URL}/api/items", headers={"Authorization": f"Bearer {token_device_2}"}).json()
    assert len(alex_device_2_items) >= 1
    print(f"   [OK] PASS: Cross-device login synced! Retrieved {len(alex_device_2_items)} items for Alex.")

    print("\n=============================================================")
    print("  ALL MULTI-USER & DATA PROTECTION TESTS PASSED SUCCESSFULLY!")
    print("=============================================================\n")

if __name__ == "__main__":
    test_isolation()
