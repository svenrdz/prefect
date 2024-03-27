from collections.abc import AsyncGenerator
from fnmatch import fnmatch
from typing import Any, Awaitable, Callable

import orjson as json
from prefect.server.admin.db import User
from rich import inspect

from prefect._vendor.fastapi import FastAPI, Request, Response, status
from prefect._vendor.starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)

RequestHook = Callable[[Request], Awaitable[Request]]
ResponseHook = Callable[[Request, Response], Awaitable[Response]]


async def consume_copy(
    gen: AsyncGenerator,
) -> tuple[list[Any], AsyncGenerator]:
    result = []
    async for item in gen:
        result.append(item)

    async def result_gen():
        for item in result:
            yield item

    return (result, result_gen())


class RouteMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable,
        pattern: str = "*",
        methods: list[str] | None = None,
        before_hook: RequestHook | None = None,
        after_hook: ResponseHook | None = None,
    ):
        super().__init__(app)
        self.pattern = pattern
        self.methods = methods or ["GET", "POST", "PATCH", "DELETE"]
        self.before_hook = before_hook
        self.after_hook = after_hook

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.scope.get("path")
        method = request.scope.get("method")
        route_matches = path is not None and fnmatch(path, self.pattern)
        method_matches = method is not None and method in self.methods
        should_hook = route_matches and method_matches
        if should_hook and self.before_hook is not None:
            request = await self.before_hook(request)
        response = await call_next(request)
        if should_hook and self.after_hook is not None:
            response = await self.after_hook(request, response)
        return response


def add_filter_route(api: FastAPI):
    async def before(request: Request) -> Request:
        # print("ENTER MIDDLEWARE")
        return request

    async def after(request: Request, response: Response) -> Response:
        if False and response.status_code == status.HTTP_200_OK:
            # inspect(response)
            contents, response.body_iterator = await consume_copy(
                response.body_iterator
            )
            for item in contents:
                try:
                    data = json.loads(item.decode())
                    inspect(data)
                    # TODO: register resource with user as owner
                    # what about groups??
                except Exception as e:
                    print(e)
        return response

    api.add_middleware(
        RouteMiddleware,
        pattern="*/filter",
        methods=["POST"],
        before_hook=before,
        after_hook=after,
    )
