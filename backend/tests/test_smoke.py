"""
Smoke tests — verificerer at appen starter og basale endpoints svarer.
Kræver ingen rigtig Supabase-forbindelse.
"""


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["crypto"] == "ok"


def test_settings_load():
    from app.core.config import settings

    assert settings.secret_key
    assert settings.encryption_key
