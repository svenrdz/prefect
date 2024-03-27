from typing import Any

import httpx

from prefect._vendor.fastapi import Depends
from prefect._vendor.fastapi_users.authentication.strategy.db import (
    AccessTokenDatabase,
    DatabaseStrategy,
)
from prefect._vendor.fastapi_users.db import SQLAlchemyUserDatabase
from prefect._vendor.fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
)
from prefect.server.admin.db import (
    AccessToken,
    OAuthAccount,
    User,
    UserManager,
)
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface


class PrefectDatabaseStrategy(DatabaseStrategy):
    def _create_access_token_dict(self, user: User) -> dict[str, Any]:
        """
        Prefect cloud uses a token's first 4 chars to determine
        whether it authentifies a user or a service account.
        pnu_* -> user
        pnb_* -> service account (bot)
        """
        token_dict = super()._create_access_token_dict(user)
        token_dict["token"] = f"pnu_{token_dict['token']}"
        return token_dict


async def get_user_db(
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context() as session:
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


async def get_access_token_db(
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context() as session:
        yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(
        get_access_token_db
    ),
) -> PrefectDatabaseStrategy:
    return PrefectDatabaseStrategy(
        access_token_db, lifetime_seconds=60 * 60 * 24
    )


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


async def get_async_client():
    async with httpx.AsyncClient() as client:
        yield client
