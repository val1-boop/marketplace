from .conftest import IDS
from .test_shop import add_address, address_ids, post


def test_payment_shows_confirmation_dialog_and_success_alert(as_bob, app):
    add_address(as_bob)
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1"})
    page = as_bob.get("/checkout").get_data(as_text=True)
    assert 'id="pay-dialog"' in page and "¿Estás seguro?" in page and "Pagar $" in page
    assert "laboratorio" not in page.lower()
    address_id = str(address_ids(app, IDS["bob"])[0])
    response = post(as_bob, "/checkout", {"address_id": address_id}, "/checkout")
    assert response.status_code == 302
    detail = as_bob.get(response.headers["Location"]).get_data(as_text=True)
    assert "¡Pago exitoso!" in detail


def test_checkout_without_addresses_redirects_to_create_one(as_bob):
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1"})
    response = as_bob.get("/checkout")
    assert response.status_code == 302 and "/addresses/new" in response.headers["Location"]


def test_checkout_post_with_invalid_address_is_a_400_with_message(as_bob):
    add_address(as_bob)
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1"})
    response = post(as_bob, "/checkout", {"address_id": "999999"}, "/checkout")
    assert response.status_code == 400
    assert "Revisa la dirección de envío elegida" in response.get_data(as_text=True)
