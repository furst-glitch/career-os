import httpx
import pytest


@pytest.fixture
async def client():
    from app.main import app  # deferred — only loaded when fixture is used (requires env vars)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
