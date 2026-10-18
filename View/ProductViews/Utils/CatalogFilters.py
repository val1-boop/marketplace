"""Enlaces de los filtros del catálogo y las "chips" de filtros activos.

Las URLs se arman con url_for() a partir de valores que ya pasaron las listas blancas
del formulario; nunca se copia texto del usuario a una URL a mano.
"""
from dataclasses import asdict

from flask import url_for

from Core.Catalog import AVAILABILITY, CATEGORIES, DEPARTMENTS

FILTER_KEYS = ("department", "category", "availability")


def make_filter_url(query):
    params = asdict(query)

    def filter_url(**changes):
        merged = dict(params, **changes)
        if merged.get("sort") == "newest":
            merged.pop("sort")
        return url_for("items.catalog", **{k: v for k, v in merged.items() if v})

    return filter_url


def active_chips(query, filter_url):
    """Lista de (etiqueta, url para quitar ese filtro)."""
    labels = {
        "department": DEPARTMENTS, "category": {k: v[0] for k, v in CATEGORIES.items()},
        "availability": AVAILABILITY,
    }
    chips = []
    if query.q:
        chips.append((f"“{query.q}”", filter_url(q="")))
    for key in FILTER_KEYS:
        value = getattr(query, key)
        if value:
            chips.append((labels[key][value], filter_url(**{key: ""})))
    return chips
