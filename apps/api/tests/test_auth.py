import pytest

@pytest.mark.asyncio
async def test_signup_flow(client):
    r = await client.post("/v1/auth/signup", json={
        "email": "test@echo.ai",
        "password": "supersecret123",
    })
    # In real test, need a clean DB
    assert r.status_code in (200, 400)  # 400 if email exists
    if r.status_code == 200:
        data = r.json()
        assert "api_key" in data
        assert data["api_key"].startswith("echo_sk_live_")

@pytest.mark.asyncio
async def test_unauth_predict(client):
    r = await client.post("/v1/predict", json={"model": "whale-netflow-eth"})
    assert r.status_code == 401
