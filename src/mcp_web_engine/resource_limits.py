"""Bound HTTP buffering, body-read time and in-flight work before endpoint parsing."""
import asyncio
import threading

from starlette.responses import JSONResponse

from .config import settings


class RequestSizeLimitMiddleware:
    def __init__(self, app):
        self.app = app
        # Nonblocking process-local admission also works across test/server loops.
        self.slots = threading.BoundedSemaphore(settings.MAX_CONCURRENT_REQUESTS)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        if not self.slots.acquire(blocking=False):
            return await JSONResponse({'error': 'SERVER_BUSY'}, 503, headers={'Retry-After': '1'})(scope, receive, send)
        try:
            return await self._http(scope, receive, send)
        finally:
            self.slots.release()

    async def _http(self, scope, receive, send):
        limit = settings.MAX_PAYLOAD_BYTES
        length = next((value for name, value in scope.get('headers', []) if name.lower() == b'content-length'), None)
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError
            except ValueError:
                return await JSONResponse({'error': 'INVALID_CONTENT_LENGTH'}, 400)(scope, receive, send)
            if size > limit:
                return await JSONResponse({'error': 'PAYLOAD_TOO_LARGE'}, 413)(scope, receive, send)
        body = bytearray()
        try:
            # One absolute deadline, not reset by a client dripping tiny chunks.
            async with asyncio.timeout(settings.REQUEST_BODY_TIMEOUT_SEC):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    chunk = message.get('body', b'')
                    if len(body) + len(chunk) > limit:
                        return await JSONResponse({'error': 'PAYLOAD_TOO_LARGE'}, 413)(scope, receive, send)
                    body.extend(chunk)
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            return await JSONResponse({'error': 'REQUEST_BODY_TIMEOUT'}, 408)(scope, receive, send)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        return await self.app(scope, bounded_receive, send)
