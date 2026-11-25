"""El cliente de Flask pide todas las páginas del catálogo."""
from Implementation.ProductServiceImplementation.ProductsApiClient import ProductsAPI

from .aws_fakes import seed_item
from .test_products_api import setup  # noqa: F401  (setup es un fixture de pytest)


def test_client_follows_all_pages(setup, monkeypatch):  # noqa: F811
    table, gateway, api = setup
    for n in range(2, 8):
        seed_item(table, f"PROD-{n:03d}", f"Producto {n}", "SEL-000001", "10.00", 1)
    monkeypatch.setattr(ProductsAPI, "PAGE_SIZE", 2)
    products = api.list_products()
    assert len(products) == 7 and len({p.product_id for p in products}) == 7
    list_calls = [r for r in gateway.requests if r[0] == "GET" and r[1].endswith("/products")]
    assert len(list_calls) == 4        # 7 productos en páginas de 2
