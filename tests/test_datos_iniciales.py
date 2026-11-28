"""Scripts SQL: /database es copia de aws/sql y ninguno guarda contraseñas ni claves."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted(path.name for path in (ROOT / "aws" / "sql").glob("*.sql"))


def _normal(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def test_database_folder_has_a_copy_of_every_sql_script():
    assert "05_mysql_datos_iniciales.sql" in SCRIPTS
    for name in SCRIPTS:
        assert _normal(ROOT / "database" / name) == _normal(ROOT / "aws" / "sql" / name), name


def test_initial_data_script_is_idempotent_and_has_no_secrets():
    sql = (ROOT / "aws" / "sql" / "05_mysql_datos_iniciales.sql").read_text(encoding="utf-8")
    assert "INSERT IGNORE INTO sellers" in sql and "DELETE" not in sql.upper() and "DROP" not in sql.upper()
    assert not re.search(r"password_hash|IDENTIFIED BY|CREATE USER|argon2", sql, re.IGNORECASE)


def test_database_readme_lists_the_initial_data_script():
    readme = (ROOT / "database" / "README.md").read_text(encoding="utf-8")
    assert "05_mysql_datos_iniciales.sql" in readme and "04_mysql_sellers.sql" in readme
