import time
import requests

PUBLIC_URL = 'https://sega-tank-implications-tomorrow.trycloudflare.com'

print('=' * 75)
print('MANUAL TESTING LIVE PUBLIC CLOUDFLARE URL:', PUBLIC_URL)
print('=' * 75)

# Step 1: Homepage Connectivity
print('\n[STEP 1] Homepage Reachability & SSL Handshake')
r1 = requests.get(PUBLIC_URL)
server_hdr = r1.headers.get("Server", "cloudflare")
print(f'GET {PUBLIC_URL} -> HTTP {r1.status_code} | Edge Server: {server_hdr}')
assert r1.status_code == 200

# Step 2: Signup
ts = int(time.time())
email = f'public_tester_{ts}@example.com'
password = 'CloudTesterPassword123!'
session = requests.Session()

print(f'\n[STEP 2] User Registration for {email}')
r2 = session.post(f'{PUBLIC_URL}/api/auth/signup', json={'email': email, 'password': password, 'display_name': 'Cloud VIP'})
print(f'POST /api/auth/signup -> HTTP {r2.status_code}')
print('User Data Created:', r2.json())
assert r2.status_code == 200

# Step 3: Login
print(f'\n[STEP 3] User Login & Session Cookie Handshake')
r3 = session.post(f'{PUBLIC_URL}/api/auth/login', json={'email': email, 'password': password})
print(f'POST /api/auth/login -> HTTP {r3.status_code}')
print('Cookies Received:', dict(session.cookies))
assert r3.status_code == 200 and 'session' in session.cookies

# Step 4: Auth Me
print('\n[STEP 4] Verify Authenticated Profile (/api/auth/me)')
r4 = session.get(f'{PUBLIC_URL}/api/auth/me')
print(f'GET /api/auth/me -> HTTP {r4.status_code}')
print('Profile Details:', r4.json())
assert r4.status_code == 200

# Step 5: Add Wardrobe Piece
print('\n[STEP 5] Add Piece to Digital Closet')
item_payload = {
    'name': 'Cashmere Camel Trench Coat',
    'category': 'topwear',
    'stored_name': f'trench_{ts}.png',
    'color': '#c29b61',
    'bytes': 48000,
    'is_manual': 1
}
r5 = session.post(f'{PUBLIC_URL}/api/items', json=item_payload)
item = r5.json()
print(f'POST /api/items -> HTTP {r5.status_code}')
print(f'Piece Created: ID {item["id"]} | {item["name"]} | Category: {item["category"]}')
assert r5.status_code == 200

# Step 6: Filter Closet
print('\n[STEP 6] Category Filtering (?category=topwear)')
r6 = session.get(f'{PUBLIC_URL}/api/items?category=topwear')
print(f'GET /api/items?category=topwear -> Found {len(r6.json())} item(s): {[i["name"] for i in r6.json()]}')
assert len(r6.json()) >= 1

# Step 7: Admin Dashboard Check
print('\n[STEP 7] Admin System Metrics over Public Internet')
admin_session = requests.Session()
admin_session.post(f'{PUBLIC_URL}/api/auth/login', json={'email': 'admin@example.com', 'password': 'AdminSecurePassword123!'})
r7 = admin_session.get(f'{PUBLIC_URL}/api/admin/stats')
print('Admin Metrics:', r7.json())
assert r7.status_code == 200

print('\n' + '=' * 75)
print('ALL PUBLIC CLOUDFLARE MANUAL TESTS PASSED 100%!')
print('=' * 75)
