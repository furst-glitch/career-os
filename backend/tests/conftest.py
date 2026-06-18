import pytest
import httpx
from app.main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c
