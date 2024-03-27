import uuid

from prefect._vendor.fastapi import Request, Response, status
from prefect._vendor.fastapi_users import BaseUserManager, UUIDIDMixin
from prefect._vendor.fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from prefect._vendor.fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyBaseAccessTokenTableUUID,
)
from prefect.server.admin.config import PREFECT_AUTH_SECRET
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.utilities.database import UUID
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.collections import AutoEnum
from sqlalchemy.orm import Mapped, relationship

# import sqlalchemy as sa

TOTO = PREFECT_AUTH_SECRET

db = provide_database_interface()


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, db.Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, db.Base):
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined"
    )


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, db.Base):
    pass


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    # reset_password_token_secret = TOTO
    # verification_token_secret = TOTO

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        redirect_uri = PREFECT_UI_URL.value()
        if request is not None:
            redirect_uri = request.session.pop("next", redirect_uri)
        if response is not None:
            response.status_code = status.HTTP_307_TEMPORARY_REDIRECT
            response.headers["Location"] = redirect_uri


# class Table(AutoEnum):
#     Flow = AutoEnum.auto()

# class Resource(db.Base):
#     about = sa.Column(UUID())
#     table = sa.Column(sa.Enum(Table))


async def create_db_and_tables():
    engine = await db.database_config.engine()

    async with engine.begin() as conn:
        await db.database_config.create_db(conn, db.Base.metadata)
