"""Filtros y funciones disponibles en todas las plantillas Jinja2.

Se registran como globales (no como context_processor) para que también funcionen
dentro de las macros. Ninguno devuelve HTML sin escapar.
"""
from Core.Catalog import (
    AVAILABILITY,
    CATEGORIES,
    CONDITIONS,
    DEPARTMENTS,
    category_class,
    category_icon,
    category_label,
    department_label,
    initials,
)
from flask import request, session
from flask_login import current_user

from View.SharedViews.Utils.Assets import asset_url


def cart_count():
    """Piezas en el carrito (copia en la sesión, solo para pintar el contador)."""
    value = session.get("cart_count", 0)
    return value if isinstance(value, int) and value > 0 else 0


def _fav_ids():
    ids = session.get("fav_ids", [])
    return ids if isinstance(ids, list) else []


def fav_count():
    return len(_fav_ids())


def is_favorite(product_id):
    """Solo decide si el corazón se pinta lleno; agregar o quitar siempre pasa por el API."""
    return product_id in _fav_ids()


def register_template_helpers(app):
    @app.template_filter("money")
    def money(value):
        try:
            return f"${value:,.2f} MXN"
        except (TypeError, ValueError):
            return "—"

    @app.template_filter("dt")
    def dt(value):
        return value.strftime("%Y-%m-%d %H:%M UTC") if value else "—"

    @app.template_filter("initials")
    def initials_filter(value):
        return initials(value)

    app.jinja_env.globals.update(
        asset_url=asset_url,
        category_label=category_label,
        category_icon=category_icon,
        category_class=category_class,
        department_label=department_label,
        condition_label=lambda c: CONDITIONS.get(c, "—"),
        DEPARTMENTS=DEPARTMENTS,
        CATEGORIES=CATEGORIES,
        AVAILABILITY=AVAILABILITY,
        # Las macros se importan sin contexto: estos proxies les dan acceso a la petición
        # y a la persona en sesión (los mismos objetos que ya ve cualquier plantilla).
        current_user=current_user,
        request=request,
        cart_count=cart_count,
        fav_count=fav_count,
        is_favorite=is_favorite,
    )
