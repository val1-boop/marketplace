"""Pago simulado visible en Flask."""
from .test_shop import buy, change, products  # noqa: F401


def test_order_detail_shows_the_simulated_payment(as_bob, app):
    order_id = buy(as_bob, app, quantity=2)
    page = as_bob.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "Pagado" in page and "37,000.00" in page
