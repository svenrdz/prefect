from httpx import AsyncClient

from prefect._vendor.fastapi import Depends, Request, status
from prefect._vendor.fastapi.exceptions import HTTPException
from prefect._vendor.fastapi.responses import RedirectResponse
from prefect._vendor.fastapi.routing import APIRouter
from prefect.server.admin.db import User
from prefect.server.admin.dependencies import (
    DatabaseStrategy,
    get_async_client,
    get_database_strategy,
)
from prefect.server.admin.users import current_active_user
from prefect.settings import PREFECT_UI_URL

# Mimics functionality of prefect cloud
cloud_app = APIRouter()


@cloud_app.get("/auth/client")
async def root(
    request: Request,
    user: User = Depends(current_active_user),
    client: AsyncClient = Depends(get_async_client),
    strategy: DatabaseStrategy = Depends(get_database_strategy),
):
    cli_url = request.query_params.get("callback")
    if cli_url is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    failure_url = cli_url + "/failure"
    success_url = cli_url + "/success"
    try:
        token = await strategy.write_token(user)
        resp = await client.post(success_url, json={"api_key": token})
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    if resp.status_code >= 400:
        await client.post(failure_url, json={"reason": resp.text})
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return RedirectResponse(PREFECT_UI_URL.value(), status.HTTP_302_FOUND)


@cloud_app.get(
    "/account/{account_id}/workspace/{workspace_id}/{full_path:path}"
)
async def cloud_ui_redirect(
    account_id: str,
    workspace_id: str,
    full_path: str,
):
    return RedirectResponse("/" + full_path)


cloud_api = APIRouter()


@cloud_api.api_route(
    "/automations/{full_path:path}",
    methods=["GET", "POST", "PATH", "DELETE"],
)
async def automations_catchall(full_path: str):
    return {}


@cloud_api.api_route(
    "/accounts/{account_id}/workspaces/{workspace_id}/{full_path:path}",
    methods=["GET", "POST", "PATCH", "DELETE"],
)
async def cloud_api_redirect(
    account_id: str,
    workspace_id: str,
    full_path: str,
):
    return RedirectResponse("/api/" + full_path)


@cloud_api.get("/me/workspaces")
async def workspaces(user: User = Depends(current_active_user)):
    return [
        dict(
            account_id=user.id,
            account_name=user.email,
            account_handle="prefect",
            workspace_id=user.id,
            workspace_name=user.email,
            workspace_description="prefect",
            workspace_handle="prefect",
        )
    ]
