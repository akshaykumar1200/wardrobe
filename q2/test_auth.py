import pytest
from backend.models import Session as SessionModel, User


def test_signup_success(client, db_session):
    res = client.post(
        "/api/auth/signup",
        json={
            "email": "freshuser@example.com",
            "password": "SuperSecretPassword123!",
            "display_name": "Fresh User"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "freshuser@example.com"
    assert data["display_name"] == "Fresh User"
    assert data["is_admin"] is False

    # Check user in database
    user = db_session.query(User).filter(User.email == "freshuser@example.com").first()
    assert user is not None
    assert "$argon2id$" in user.password_hash


def test_signup_short_password_fails(client):
    res = client.post(
        "/api/auth/signup",
        json={
            "email": "shortpass@example.com",
            "password": "short",
            "display_name": "Short Password"
        }
    )
    assert res.status_code == 422


def test_signup_duplicate_email_fails(client, user_a):
    res = client.post(
        "/api/auth/signup",
        json={
            "email": "usera@example.com",
            "password": "AnotherSecret123!",
            "display_name": "Imposter A"
        }
    )
    assert res.status_code == 400
    assert "Email already registered" in res.json()["detail"]


def test_login_success(client, user_a):
    res = client.post(
        "/api/auth/login",
        json={
            "email": "usera@example.com",
            "password": "PasswordA123!"
        }
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["user"]["email"] == "usera@example.com"
    assert "session" in res.cookies


def test_login_wrong_password_fails(client, user_a):
    res = client.post(
        "/api/auth/login",
        json={
            "email": "usera@example.com",
            "password": "WrongPassword999!"
        }
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_login_nonexistent_user_fails(client):
    res = client.post(
        "/api/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "PasswordA123!"
        }
    )
    assert res.status_code == 401


def test_get_me_authenticated(auth_client_a, user_a):
    res = auth_client_a.get("/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == user_a.id
    assert data["email"] == user_a.email
    assert data["display_name"] == user_a.display_name


def test_get_me_unauthenticated_fails(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_patch_me_display_name(auth_client_a, user_a, db_session):
    res = auth_client_a.patch("/api/auth/me", json={"display_name": "Updated Alpha Name"})
    assert res.status_code == 200
    assert res.json()["display_name"] == "Updated Alpha Name"

    db_session.refresh(user_a)
    assert user_a.display_name == "Updated Alpha Name"


def test_logout_invalidates_session(auth_client_a, db_session):
    cookie_token = auth_client_a.cookies.get("session")
    assert cookie_token is not None

    res = auth_client_a.post("/api/auth/logout")
    assert res.status_code == 200

    # Verify session row was removed from database
    session_row = db_session.query(SessionModel).filter(SessionModel.token == cookie_token).first()
    assert session_row is None

    # Subsequent call to /me using the old client must return 401
    res_after = auth_client_a.get("/api/auth/me")
    assert res_after.status_code == 401
