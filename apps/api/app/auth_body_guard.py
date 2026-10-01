"""Bound account JSON input before parsing or password hashing."""

from uuid import uuid4
from starlette.responses import JSONResponse
from app.contracts import ApiError


class AuthBodyGuard:
    def __init__(self, app, max_bytes=16384):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root):
            path = path[len(root) :]
        private = (
            path.startswith("/api/v1/auth/")
            or path == "/api/v1/projects"
            or path.startswith("/api/v1/projects/")
        )
        if scope["type"] == "http" and private:
            downstream = send

            async def private_send(message):
                if message["type"] == "http.response.start":
                    message = {
                        **message,
                        "headers": [
                            (key, value)
                            for key, value in message.get("headers", [])
                            if key.lower() != b"cache-control"
                        ]
                        + [(b"cache-control", b"private, no-store")],
                    }
                await downstream(message)

            send = private_send
        bounded = path.startswith("/api/v1/auth/") or path == "/api/v1/projects"
        if (
            scope["type"] != "http"
            or not bounded
            or scope.get("method") not in ("POST", "PATCH", "DELETE")
        ):
            return await self.app(scope, receive, send)

        async def reject(status, code, message):
            body = ApiError(code=code, message=message, request_id=uuid4()).model_dump(
                mode="json"
            )
            await JSONResponse(
                body, status_code=status, headers={"Cache-Control": "private, no-store"}
            )(scope, receive, send)

        if path == "/api/v1/auth/logout":
            # Body is not consumed by logout; reject a submitted body as input.
            expected_json = False
        else:
            expected_json = True
        headers = scope.get("headers", [])
        types = [
            value.decode("latin-1")
            for key, value in headers
            if key.lower() == b"content-type"
        ]
        if expected_json and (
            len(types) != 1
            or types[0].split(";")[0].strip().lower() != "application/json"
        ):
            return await reject(415, "validation_error", "A JSON request is required")
        lengths = [value for key, value in headers if key.lower() == b"content-length"]
        try:
            if len(lengths) > 1 or (
                lengths
                and (not lengths[0].isdigit() or int(lengths[0]) > self.max_bytes)
            ):
                return await reject(413, "validation_error", "Request is too large")
        except ValueError:
            return await reject(413, "validation_error", "Request is too large")
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            part = message.get("body", b"")
            size += len(part)
            if size > self.max_bytes:
                return await reject(413, "validation_error", "Request is too large")
            chunks.append(part)
            if not message.get("more_body", False):
                break
        if path == "/api/v1/auth/logout" and size:
            return await reject(422, "validation_error", "This request has no body")
        delivered = False
        body = b"".join(chunks)

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
