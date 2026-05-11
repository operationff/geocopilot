import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_login_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup_resp = await client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User",
        })
        assert signup_resp.status_code == 201
        tokens = signup_resp.json()
        assert "access_token" in tokens

        login_resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123",
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

        bad_login = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert bad_login.status_code == 401
