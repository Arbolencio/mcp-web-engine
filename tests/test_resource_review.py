"""Resource-admission regression tests independent of real network/credentials."""
import asyncio
from types import SimpleNamespace

import pytest

from mcp_web_engine.resource_limits import RequestSizeLimitMiddleware


@pytest.mark.asyncio
async def test_concurrent_work_is_rejected_and_cancelled_slot_released(monkeypatch):
    monkeypatch.setattr('mcp_web_engine.resource_limits.settings', SimpleNamespace(MAX_CONCURRENT_REQUESTS=1, MAX_PAYLOAD_BYTES=1000, REQUEST_BODY_TIMEOUT_SEC=1))
    entered = asyncio.Event()
    release = asyncio.Event()
    async def app(scope, receive, send):
        entered.set()
        await release.wait()
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    messages = []
    async def send(message):
        messages.append(message)
    middleware = RequestSizeLimitMiddleware(app)
    scope = {'type': 'http', 'headers': []}
    active = asyncio.create_task(middleware(scope, receive, send))
    await entered.wait()
    await middleware(scope, receive, send)
    assert messages[0]['status'] == 503
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active
    release.set()
    messages.clear()
    await middleware(scope, receive, send)
    assert not messages, 'The cancelled request leaked its concurrency slot'


@pytest.mark.asyncio
async def test_dripping_chunks_cannot_extend_body_deadline(monkeypatch):
    monkeypatch.setattr('mcp_web_engine.resource_limits.settings', SimpleNamespace(MAX_CONCURRENT_REQUESTS=1, MAX_PAYLOAD_BYTES=1000, REQUEST_BODY_TIMEOUT_SEC=.05))
    messages = []
    async def receive():
        await asyncio.sleep(.01)
        return {'type': 'http.request', 'body': b'x', 'more_body': True}
    async def send(message):
        messages.append(message)
    async def app(scope, receive, send):
        raise AssertionError('Incomplete request reached the app')
    await asyncio.wait_for(RequestSizeLimitMiddleware(app)({'type': 'http', 'headers': []}, receive, send), .5)
    assert messages[0]['status'] == 408
