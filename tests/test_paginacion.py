"""Listado de productos del API por páginas (limit y cursor)."""
import pytest

from .aws_fakes import seed_item
from .test_lambdas import call, env  # noqa: F401  (env es un fixture de pytest)


def _seed_many(table, count, seller="SEL-000002"):
    for n in range(100, 100 + count):
        seed_item(table, f"PROD-{n:05d}", f"Producto de prueba {n}", seller, "10.00", 3)


def _read_all_pages(lambdas, limit, query=None):
    seen, cursor, pages = [], None, 0
    while True:
        params = dict(query or {}, limit=str(limit))
        if cursor:
            params["cursor"] = cursor
        status, body = call(lambdas, "lambdaListProducts", "GET", "/products", query=params)
        assert status == 200
        assert len(body["productos"]) <= limit
        seen += [p["product_id"] for p in body["productos"]]
        pages += 1
        cursor = body["next_cursor"]
        if not cursor:
            return seen, pages
        assert pages < 100, "la paginación no termina"


def test_list_paginates_all_products_without_repeats(env):  # noqa: F811
    table, lambdas = env
    _seed_many(table, 25)
    seen, pages = _read_all_pages(lambdas, 10)
    assert len(seen) == 27 and len(set(seen)) == 27   # 2 de la fixture + 25
    assert pages == 3


def test_list_paginates_by_seller(env):  # noqa: F811
    table, lambdas = env
    _seed_many(table, 25, seller="SEL-000002")
    seen, pages = _read_all_pages(lambdas, 10, {"seller_id": "SEL-000002"})
    assert len(seen) == 26 and len(set(seen)) == 26   # 25 + PROD-002
    assert pages == 3


def test_list_without_limit_keeps_the_old_behaviour(env):  # noqa: F811
    _, lambdas = env
    status, body = call(lambdas, "lambdaListProducts", "GET", "/products")
    assert status == 200 and len(body["productos"]) == 2 and body["next_cursor"] is None


@pytest.mark.parametrize("limit", ["0", "501", "-1", "abc", "1.5", "5; DROP"])
def test_list_rejects_bad_limit(env, limit):  # noqa: F811
    _, lambdas = env
    status, _ = call(lambdas, "lambdaListProducts", "GET", "/products", query={"limit": limit})
    assert status == 400


@pytest.mark.parametrize("cursor", ["%%%", "x" * 401, "e30", "bm90LWpzb24", "W10"])
def test_list_rejects_forged_cursors(env, cursor):  # noqa: F811
    _, lambdas = env
    status, _ = call(lambdas, "lambdaListProducts", "GET", "/products", query={"limit": "5", "cursor": cursor})
    assert status == 400
