import uuid
import warnings
from fnmatch import fnmatch

from prefect._vendor.fastapi import Depends, Request
from prefect._vendor.fastapi_users import FastAPIUsers
from prefect._vendor.fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
)
from prefect._vendor.httpx_oauth.clients.openid import OpenID
from prefect.server.admin.config import (
    PREFECT_AUTH_COOKIE_MAX_AGE,
    PREFECT_AUTH_COOKIE_NAME,
    PREFECT_AUTH_OIDC_CLIENT_ID,
    PREFECT_AUTH_OIDC_CLIENT_SECRET,
    PREFECT_AUTH_OIDC_URL,
)
from prefect.server.admin.db import User  # , UserManager
from prefect.server.admin.dependencies import (
    get_database_strategy,
    get_user_manager,
)

bearer_transport = BearerTransport(tokenUrl="auth/login")
cookie_transport = CookieTransport(
    cookie_name=PREFECT_AUTH_COOKIE_NAME,
    cookie_max_age=PREFECT_AUTH_COOKIE_MAX_AGE,
)
bearer_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)
cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)


def _get_oidc_client():
    if (
        PREFECT_AUTH_OIDC_CLIENT_ID is None
        or PREFECT_AUTH_OIDC_CLIENT_SECRET is None
        or PREFECT_AUTH_OIDC_URL is None
    ):
        warnings.warn(
            """
            OpenID Connect is disabled.
            To enable it, set these environment variables:
                PREFECT_AUTH_OIDC_CLIENT_ID
                PREFECT_AUTH_OIDC_CLIENT_SECRET
                PREFECT_AUTH_OIDC_URL
            """.strip()
        )
        return False
    else:
        return OpenID(
            PREFECT_AUTH_OIDC_CLIENT_ID,
            PREFECT_AUTH_OIDC_CLIENT_SECRET,
            PREFECT_AUTH_OIDC_URL,
        )


class _OIDC:
    def __init__(self):
        self.is_setup = False
        self._client = None

    @property
    def client(self):
        if not self.is_setup:
            self._client = _get_oidc_client()
            self.is_setup = True
        return self._client


OIDC = _OIDC()

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [bearer_backend, cookie_backend],
)

current_active_user = fastapi_users.current_user(active=True, verified=True)
current_active_optional_user = fastapi_users.current_user(
    active=True, optional=True
)
current_superuser = fastapi_users.current_user(active=True, superuser=True)


async def set_user(
    request: Request,
    user: User | None = Depends(current_active_optional_user),
    # user_manager: UserManager = Depends(get_user_manager),
):
    print(f"SETTING USER for {request.url}")
    request.state.user = user


def get_route_policy(
    allow: list[str],
    protect: list[str],
    superuser: list[str],
    raises: Exception,
):
    async def policy(
        request: Request,
        user: User | None = Depends(current_active_optional_user),
    ):
        # print(f"checking policy for    {request.scope.get('path')}")
        if (path := request.scope.get("path")) is None:
            # print("ERROR: no path")
            raise raises
        is_superuser = any([fnmatch(path, pattern) for pattern in superuser])
        if user is None:
            is_allowed = any([fnmatch(path, pattern) for pattern in allow])
            if is_allowed:
                # print("OK: route is allowed")
                return
            is_protected = any([fnmatch(path, pattern) for pattern in protect])
            if is_protected or is_superuser:
                # print("ERROR: route is protected")
                raise raises
        else:
            if is_superuser and not user.is_superuser:
                raise raises

    return policy
