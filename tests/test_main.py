import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import json
from unittest.mock import patch, AsyncMock

from main import handle_health

@pytest.mark.asyncio
async def test_handle_health():
    with patch('main.bot') as mock_bot, \
         patch('main.datetime') as mock_datetime:

        mock_bot.is_ready.return_value = True
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00+05:30"

        app = web.Application()
        app.router.add_get('/health', handle_health)

        server = TestServer(app)
        async with TestClient(server) as client:
            resp = await client.get('/health')
            assert resp.status == 200

            data = await resp.json()
            assert data == {
                "status": "ok",
                "agent": "Peter Thiel",
                "bot_online": True,
                "server_time_ist": "2023-01-01T12:00:00+05:30"
            }
