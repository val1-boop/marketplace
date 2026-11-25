"""Pago simulado visible en Flask."""
from .test_shop import buy, change, products  # noqa: F401


def test_order_detail_shows_the_simulated_payment(as_bob, app):
    order_id = buy(as_bob, app, quantity=2)
    page = as_bob.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "Pagado" in page and "37,000.00" in page


def test_cancelling_an_order_keeps_the_payment_record(as_bob, app):
    order_id = buy(as_bob, app)
    assert change(as_bob, order_id, "cancel", "Me equivoque de modelo").status_code == 302
    page = as_bob.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "Pagado" in page          # el pago queda como historial
    assert products(app)["PROD-001"]["stock"] == 7   # y las piezas regresaron
