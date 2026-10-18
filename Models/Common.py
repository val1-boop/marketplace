"""Utilidades compartidas por los modelos SQL."""
from datetime import datetime, timezone


def utcnow():
    """Fecha y hora UTC sin zona (las columnas DATETIME de MySQL no guardan zona)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sql_in(column, values):
    """Texto de un CHECK ... IN (...) con valores fijos del código (nunca del usuario)."""
    return f"{column} IN ({', '.join(repr(v) for v in values)})"
