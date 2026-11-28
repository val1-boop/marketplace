"""Textos corregidos: plural de opiniones, SKU/códigos internos fuera de las pantallas del pedido."""
from .test_shop import buy, products  # noqa: F401


def test_product_page_uses_correct_plural_for_zero_reviews(client):
    page = client.get("/items/PROD-001").get_data(as_text=True)
    assert "0 opiniones" in page and "opiniónes" not in page


def test_order_detail_hides_the_internal_product_code(as_bob, app):
    order_id = buy(as_bob, app)
    page = as_bob.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "PROD-001 ·" not in page and "×" in page


def test_sales_page_hides_the_seller_code(as_alice):
    page = as_alice.get("/sales/").get_data(as_text=True)
    assert "SEL-000001" not in page and "Prepara y envía los pedidos que recibió tu tienda." in page
