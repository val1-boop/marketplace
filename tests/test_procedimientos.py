"""Procedimientos almacenados de RDS MySQL (aws/sql/06_mysql_procedimientos.sql) y su uso desde la app.

Las pruebas corren con SQLite, que no tiene procedimientos: aquí se comprueba el script, que la app
use el procedimiento cuando la base es MySQL (simulado) y el manejo de errores. Los procedimientos reales se
probaron a mano contra un MySQL 8.0 de verdad: el script (26 casos) y la app completa (14 casos).
"""
import re
from pathlib import Path

import pymysql
import pytest
from sqlalchemy.exc import DBAPIError

from Core.Extensions import db
from Implementation.SharedImplementation import StoredProcedures
from Models import Seller

from .conftest import post_form

SQL = (Path(__file__).resolve().parents[1] / "aws" / "sql" / "06_mysql_procedimientos.sql").read_text(encoding="utf-8")


def test_script_defines_both_procedures_with_least_privilege():
    assert re.findall(r"CREATE PROCEDURE (\w+)", SQL) == ["sp_guardar_tienda", "sp_resumen_cuentas"]
    assert len(re.findall(r"^SQL SECURITY INVOKER$", SQL, re.MULTILINE)) == 2   # permisos de mkt_app, sin extras
    assert "SQL SECURITY DEFINER" not in SQL
    assert "GRANT EXECUTE ON PROCEDURE marketplace.sp_guardar_tienda TO 'mkt_app'@'%'" in SQL
    assert "GRANT EXECUTE ON PROCEDURE marketplace.sp_resumen_cuentas TO 'mkt_app'@'%'" in SQL
    assert "ON DUPLICATE KEY UPDATE" in SQL and "SIGNAL SQLSTATE '45000'" in SQL


def test_script_has_no_secrets_and_no_destructive_statements():
    assert not re.search(r"IDENTIFIED BY|password|CREATE USER|argon2", SQL, re.IGNORECASE)
    assert not re.search(r"\b(DELETE FROM|TRUNCATE|DROP TABLE|DROP DATABASE)\b", SQL, re.IGNORECASE)


def test_sqlite_does_not_use_procedures(app):
    with app.app_context():
        assert StoredProcedures.available() is False


def _fake_session(dialect):
    class Bind:
        class dialect:  # noqa: N801  (imita session.get_bind().dialect.name)
            name = dialect

    class Session:
        def get_bind(self):
            return Bind()

    return Session()


def test_available_only_for_mysql():
    assert StoredProcedures.available(_fake_session("mysql")) is True
    assert StoredProcedures.available(_fake_session("sqlite")) is False
    assert StoredProcedures.available(_fake_session("postgresql")) is False


def test_store_is_saved_with_the_procedure_on_mysql(as_alice, app, monkeypatch):
    calls = []
    monkeypatch.setattr(StoredProcedures, "available", lambda session=None: True)
    monkeypatch.setattr(StoredProcedures, "save_store", lambda *args: calls.append(args))
    response = post_form(as_alice, "/store/edit", {"store_name": "Tecnología Alice", "description": "Equipos.",
                                                   "seller_id": "SEL-999999", "user_id": "otro"})
    assert response.status_code == 302
    # El código de vendedor y el usuario salen de la sesión; lo que mande el navegador se ignora.
    assert calls == [("00000000-0000-4000-8000-000000000002", "SEL-000001", "Tecnología Alice", "Equipos.")]
    with app.app_context():
        assert db.session.scalars(db.select(Seller)).all() == []     # no pasó por el ORM


def test_procedure_rejection_is_shown_to_the_person(as_alice, monkeypatch):
    def reject(*args):
        raise ValueError("El nombre de la tienda debe tener de 3 a 80 caracteres")

    monkeypatch.setattr(StoredProcedures, "available", lambda session=None: True)
    monkeypatch.setattr(StoredProcedures, "save_store", reject)
    response = post_form(as_alice, "/store/edit", {"store_name": "Tienda válida", "description": ""})
    page = response.get_data(as_text=True)
    assert response.status_code == 200 and "debe tener de 3 a 80 caracteres" in page
    assert "se guardaron" not in page


def test_admin_dashboard_uses_the_summary_procedure_on_mysql(as_admin, monkeypatch):
    summary = {"usuarios": 42, "activos": 40, "suspendidos": 1, "bloqueados": 1, "administradores": 2, "tiendas": 30}
    monkeypatch.setattr(StoredProcedures, "available", lambda session=None: True)
    monkeypatch.setattr(StoredProcedures, "account_summary", lambda session=None: summary)
    page = as_admin.get("/dashboard").get_data(as_text=True)
    assert "<strong>42</strong><span>usuarios" in page


def test_procedure_errors_become_value_errors_and_roll_back():
    class Session:
        rolled_back = False

        def __init__(self, error):
            self.error = error

        def execute(self, *args, **kwargs):
            raise DBAPIError("CALL sp_guardar_tienda(...)", {}, self.error)

        def rollback(self):
            self.rolled_back = True

    rejected = Session(pymysql.err.OperationalError(1644, "El codigo de vendedor no es valido"))
    with pytest.raises(ValueError, match="no es valido"):
        StoredProcedures.save_store("u", "SEL-1", "Tienda", "", session=rejected)
    assert rejected.rolled_back
    other = Session(pymysql.err.OperationalError(1213, "Deadlock"))        # un error distinto no se disfraza
    with pytest.raises(DBAPIError):
        StoredProcedures.save_store("u", "SEL-000001", "Tienda", "", session=other)
    assert other.rolled_back
    missing = Session(pymysql.err.ProgrammingError(1305, "PROCEDURE marketplace.sp_guardar_tienda does not exist"))
    with pytest.raises(StoredProcedures.ProcedureMissing):
        StoredProcedures.save_store("u", "SEL-000001", "Tienda", "", session=missing)
    with pytest.raises(StoredProcedures.ProcedureMissing):
        StoredProcedures.account_summary(missing)
    assert missing.rolled_back
    denied = Session(pymysql.err.OperationalError(1370, "execute command denied to user 'mkt_app'@'%'"))
    with pytest.raises(StoredProcedures.ProcedureMissing):      # lo que MySQL responde si falta el procedimiento
        StoredProcedures.save_store("u", "SEL-000001", "Tienda", "", session=denied)


def test_summary_is_returned_as_plain_integers():
    class Result:
        def __init__(self, row):
            self.row = row

        def mappings(self):
            return self

        def first(self):
            return self.row

    class Session:
        def __init__(self, row):
            self.row = row

        def execute(self, *args, **kwargs):
            return Result(self.row)

    row = {"usuarios": 5, "activos": 4, "suspendidos": 1, "bloqueados": None, "administradores": 1, "tiendas": 3}
    assert StoredProcedures.account_summary(Session(row)) == {
        "usuarios": 5, "activos": 4, "suspendidos": 1, "bloqueados": 0, "administradores": 1, "tiendas": 3}
    assert set(StoredProcedures.account_summary(Session(None)).values()) == {0}


def _missing(*args, **kwargs):
    raise StoredProcedures.ProcedureMissing


def test_without_the_script_the_store_is_still_saved_with_the_orm(as_alice, app, monkeypatch):
    monkeypatch.setattr(StoredProcedures, "available", lambda session=None: True)
    monkeypatch.setattr(StoredProcedures, "save_store", _missing)
    assert post_form(as_alice, "/store/edit", {"store_name": "Tecnología Alice", "description": ""}).status_code == 302
    with app.app_context():
        assert [s.store_name for s in db.session.scalars(db.select(Seller)).all()] == ["Tecnología Alice"]


def test_without_the_script_the_dashboard_still_counts_accounts(as_admin, monkeypatch):
    monkeypatch.setattr(StoredProcedures, "available", lambda session=None: True)
    monkeypatch.setattr(StoredProcedures, "account_summary", _missing)
    page = as_admin.get("/dashboard").get_data(as_text=True)
    assert page.count("<span>usuarios") == 1
