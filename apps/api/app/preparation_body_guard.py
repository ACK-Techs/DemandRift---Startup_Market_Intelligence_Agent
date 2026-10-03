"""Strict 64 KiB JSON intake for preparation mutations only."""

import json
from uuid import uuid4

from starlette.responses import JSONResponse
from app.contracts import ApiError


class PreparationBodyGuard:
    def __init__(self, app, max_bytes=65536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "").removeprefix(scope.get("root_path", ""))
        parts = path.split("/")
        selected = (
            len(parts) >= 6
            and parts[1:4] == ["api", "v1", "projects"]
            and (parts[5] == "research" or parts[5] == "preparation-mutations")
        )
        selected = selected or path in ("/api/v1/settings", "/api/v1/dashboard")
        if not selected:
            return await self.app(scope, receive, send)
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
        if scope.get("method") not in ("POST", "PATCH", "PUT", "DELETE"):
            return await self.app(scope, receive, send)

        async def reject(status, message):
            body = ApiError(
                code="validation_error", message=message, request_id=uuid4()
            ).model_dump(mode="json")
            await JSONResponse(body, status_code=status)(scope, receive, send)

        headers = scope.get("headers", [])
        types = [
            v.decode("latin-1") for k, v in headers if k.lower() == b"content-type"
        ]
        encodings = [
            v.lower().strip() for k, v in headers if k.lower() == b"content-encoding"
        ]
        if (
            len(types) != 1
            or types[0].split(";")[0].strip().lower() != "application/json"
            or (encodings and encodings != [b"identity"])
        ):
            return await reject(415, "A JSON request is required")
        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        try:
            if len(lengths) > 1 or (
                lengths
                and (not lengths[0].isdigit() or int(lengths[0]) > self.max_bytes)
            ):
                return await reject(413, "Request is too large")
        except ValueError:
            return await reject(413, "Request is too large")
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            part = message.get("body", b"")
            size += len(part)
            if size > self.max_bytes:
                return await reject(413, "Request is too large")
            chunks.append(part)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        def object_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON field")
                result[key] = value
            return result

        def invalid_constant(value):
            raise ValueError("Non-finite JSON number")

        try:
            parsed = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=object_pairs,
                parse_constant=invalid_constant,
            )
            if type(parsed) is not dict:
                raise ValueError()
            # JSON escape sequences can contain lone surrogates, and exponent
            # overflow can produce infinity without parse_constant being called.
            json.dumps(parsed, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, UnicodeError, RecursionError):
            return await reject(422, "Check the submitted values")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
