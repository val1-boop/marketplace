"""Llamadas a los procedimientos almacenados de RDS MySQL (aws/sql/06_mysql_procedimientos.sql).

- sp_guardar_tienda: crea o actualiza la tienda de un vendedor de forma atómica y validada.
- sp_resumen_cuentas: consulta consolidada de cuentas y tiendas para el panel del administrador.

Los valores viajan siempre como parámetros (nunca se arma SQL con texto). Los procedimientos solo
existen en MySQL: con SQLite (pruebas y modo local sin AWS) `available()` es falso y las
implementaciones usan su camino con el ORM, que hace lo mismo. Si en RDS todavía no se ejecutó el
script 06, la llamada lanza ProcedureMissing y la implementación también cae al ORM (con un aviso en el registro).
"""
import logging

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from Core.Extensions import db

_SAVE_STORE = text("CALL sp_guardar_tienda(:seller_id, :user_id, :store_name, :description)")
_ACCOUNT_SUMMARY = text("CALL sp_resumen_cuentas()")
_SIGNAL_ERROR = 1644  # error que lanza SIGNAL SQLSTATE '45000' dentro del procedimiento
# El procedimiento no existe (1305) o mkt_app no tiene EXECUTE sobre él (1370: es lo que MySQL responde cuando
# falta crearlo, porque sin el procedimiento tampoco hay permiso). En ambos casos falta el script 06.
_UNAVAILABLE_PROCEDURE = (1305, 1370)
log = logging.getLogger("marketplace.procedures")
_SUMMARY_KEYS = ("usuarios", "activos", "suspendidos", "bloqueados", "administradores", "tiendas")


class ProcedureMissing(Exception):
    """El procedimiento no existe o mkt_app no puede ejecutarlo: falta aws/sql/06_mysql_procedimientos.sql."""


def _translate(error, session):
    """Convierte el error de MySQL: SIGNAL del procedimiento -> ValueError; sin procedimiento -> ProcedureMissing."""
    session.rollback()
    args = getattr(error.orig, "args", ())
    if len(args) == 2 and args[0] == _SIGNAL_ERROR:
        raise ValueError(str(args[1])) from error
    if args and args[0] in _UNAVAILABLE_PROCEDURE:
        log.warning("Falta ejecutar aws/sql/06_mysql_procedimientos.sql (o dar EXECUTE a mkt_app): se usa el ORM")
        raise ProcedureMissing from error
    raise error


def available(session=None):
    """True cuando la base es MySQL (RDS), que es donde viven los procedimientos."""
    return (session or db.session).get_bind().dialect.name == "mysql"


def save_store(user_id, seller_id, store_name, description, session=None):
    """Llama a sp_guardar_tienda. Si el procedimiento rechaza los datos lanza ValueError con su mensaje."""
    session = session or db.session
    try:
        session.execute(_SAVE_STORE, {"seller_id": seller_id, "user_id": user_id,
                                      "store_name": store_name, "description": description or ""})
    except DBAPIError as error:
        _translate(error, session)


def account_summary(session=None):
    """Llama a sp_resumen_cuentas y devuelve sus conteos como un diccionario de enteros."""
    session = session or db.session
    try:
        row = session.execute(_ACCOUNT_SUMMARY).mappings().first()
    except DBAPIError as error:
        _translate(error, session)
    return {key: int(row[key] or 0) for key in _SUMMARY_KEYS} if row else dict.fromkeys(_SUMMARY_KEYS, 0)
