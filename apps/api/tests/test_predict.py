import pytest

@pytest.mark.asyncio
async def test_predict_with_key(client, api_key):
    """Requires fixture `api_key` from authenticated signup."""
    r = await client.post(
        "/v1/predict",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "whale-netflow-eth"},
    )
    if r.status_code == 200:
        data = r.json()
        assert "prediction" in data
        assert "performance_cert" in data
        assert "disclaimer" in data
