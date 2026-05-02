from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from core.security import decode_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.auth_payload = None
        request.state.auth_error = None

        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                try:
                    request.state.auth_payload = decode_token(token)
                except ValueError as error:
                    request.state.auth_error = str(error)

        return await call_next(request)
