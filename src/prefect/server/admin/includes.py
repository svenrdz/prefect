from typing import cast

from prefect._vendor.fastapi import Depends, FastAPI, Request, status
from prefect._vendor.fastapi.exceptions import HTTPException
from prefect._vendor.fastapi.responses import RedirectResponse
from prefect._vendor.fastapi.routing import Mount
from prefect._vendor.starlette.datastructures import URL
from prefect._vendor.starlette.middleware.sessions import SessionMiddleware
from prefect._vendor.starlette.staticfiles import StaticFiles
from prefect.server.admin.cloud import cloud_api, cloud_app
from prefect.server.admin.db import TOTO
from prefect.server.admin.dependencies import get_async_client
from prefect.server.admin.users import (
    OIDC,
    bearer_backend,
    cookie_backend,
    fastapi_users,
    get_route_policy,
)


class RequiresLogin(Exception):
    pass


async def redirect_login(request: Request, exc: Exception):
    # redirect_uri = (
    #     request.query_params.get("next")  #
    #     or request.query_params.get("callback")
    #     or PREFECT_UI_URL.value()
    # )
    request.session["next"] = request.url._url
    return RedirectResponse(request.url_for("login"), status.HTTP_302_FOUND)


api_policy = get_route_policy(
    allow=[],
    protect=["*"],
    superuser=["*/admin/*"],
    raises=HTTPException(status.HTTP_401_UNAUTHORIZED),
    # debug=True,
)
ui_policy = get_route_policy(
    # allow=["/auth/client", "/ui-settings"],
    allow=[],
    protect=["*"],
    superuser=[],
    raises=RequiresLogin("You must be logged in to access this"),
)


def add_policy_api(api: FastAPI):
    if OIDC.client is None:
        return
    api.router.dependencies.append(Depends(api_policy))


def add_policy_ui(ui: FastAPI):
    if OIDC.client is None:
        return
    ui.add_exception_handler(RequiresLogin, redirect_login)
    ui.router.dependencies.append(Depends(ui_policy))


def include_all(app: FastAPI, ui: FastAPI, api: FastAPI):
    if OIDC.client is None:
        return
    app.add_middleware(SessionMiddleware, secret_key=TOTO)

    @app.get("/login", name="login")
    async def oidc_login(
        request: Request,
        client=Depends(get_async_client),
    ):
        authorize = request.url_for("oauth:openid.cookie.authorize")
        resp = await client.get(authorize._url)
        authorization_url = URL(resp.json()["authorization_url"])
        return RedirectResponse(authorization_url, status.HTTP_302_FOUND)

    ui.include_router(cloud_app, prefix="", tags=["cloud"])
    api.include_router(cloud_api, prefix="", tags=["cloud"])

    # oauth (OpenID Connect)
    app.include_router(
        fastapi_users.get_oauth_router(
            OIDC.client,
            bearer_backend,
            TOTO,
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/auth/bearer",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_oauth_router(
            OIDC.client,
            cookie_backend,
            TOTO,
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/auth/cookie",
        tags=["auth"],
    )

    mount = [route for route in ui.routes if isinstance(route, Mount)][0]
    ui.routes.pop(ui.routes.index(mount))
    static_app = cast(StaticFiles, mount.app)

    # declare catch-all route to dispatch static front-end after all
    # authorization routes have been declared properly
    @ui.get("/{_:path}")
    async def ui_root(
        _: str,
        request: Request,
    ):
        path = static_app.get_path(request.scope)
        print(f"UI:routing      /{path}")
        return await static_app.get_response(path, request.scope)
