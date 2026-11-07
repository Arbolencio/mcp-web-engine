"""Bound HTTP request buffering independently of endpoint/auth parsing."""
from starlette.responses import JSONResponse

from .config import settings


class RequestSizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
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
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        return await self.app(scope, bounded_receive, send)
