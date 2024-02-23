from typing import Any

from prefect._vendor.fastapi.applications import FastAPI
from prefect.utilities.asyncutils import sync


def create_admin_app() -> FastAPI:
    from starlette_admin.contrib.sqla import Admin, ModelView
    from starlette_admin.contrib.sqla.converters import ModelConverter
    from starlette_admin.converters import converts
    from starlette_admin.fields import BaseField, StringField

    from prefect.server.database.dependencies import provide_database_interface

    class Converter(ModelConverter):
        @converts(
            "String",
            "prefect.server.utilities.database.UUID",
            "sqlalchemy.sql.sqltypes.Uuid",
            "sqlalchemy.dialects.postgresql.base.UUID",
            "sqlalchemy.dialects.postgresql.base.UUID",
            "sqlalchemy.dialects.postgresql.base.MACADDR",
            "sqlalchemy.dialects.postgresql.types.MACADDR",
            "sqlalchemy.dialects.postgresql.base.INET",
            "sqlalchemy.dialects.postgresql.types.INET",
            "sqlalchemy_utils.types.locale.LocaleType",
            "sqlalchemy_utils.types.ip_address.IPAddressType",
            "sqlalchemy_utils.types.uuid.UUIDType",
        )  # includes Unicode
        def conv_string(self, *args: Any, **kwargs: Any) -> BaseField:
            return StringField(
                **self._field_common(*args, **kwargs),
                **self._string_common(*args, **kwargs),
            )

    converter = Converter()

    db = provide_database_interface()
    engine = sync(db.engine)
    admin = Admin(engine, title="Prefect admin")
    admin.add_view(ModelView(db.Flow, converter=converter))
    admin.add_view(ModelView(db.FlowRun, converter=converter))
    admin.add_view(ModelView(db.TaskRun, converter=converter))
    admin.add_view(ModelView(db.Deployment, converter=converter))
    admin.add_view(ModelView(db.BlockType, converter=converter))
    admin.add_view(ModelView(db.FlowRunInput, converter=converter))
    return admin


# def add_admin_views(app: FastAPI):
#     from sqladmin import Admin, ModelView
#
#     from prefect.server.database.dependencies import provide_database_interface
#
#     db = provide_database_interface()
#     engine = sync(db.engine)
#     admin = Admin(app, engine)
#
#     class WorkPoolAdmin(ModelView, model=db.WorkPool):
#         column_list = []
#
#     admin.add_view(ModelView(db.WorkPool))
#     return admin
