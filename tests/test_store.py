"""Datos de la tienda del vendedor (entidad Vendedores)."""
import pytest

from Core.Extensions import db
from Models import Seller

from .conftest import post_form


def _save(client, **data):
    payload = {"store_name": "Tecnología Alice", "description": "Equipos nuevos y usados."}
    payload.update(data)
    return post_form(client, "/store/edit", payload)


def test_seller_saves_store_and_name_appears_in_product_page(as_alice, app, client):
    assert _save(as_alice).status_code == 302
    with app.app_context():
        row = db.session.get(Seller, "SEL-000001")
        assert row.store_name == "Tecnología Alice" and row.user_id.endswith("0002")
    page = client.get("/items/PROD-001").get_data(as_text=True)
    assert "Vendido por Tecnología Alice" in page


def test_store_can_be_updated_without_creating_duplicates(as_alice, app):
    _save(as_alice)
    _save(as_alice, store_name="Nuevo nombre de tienda")
    with app.app_context():
        rows = db.session.scalars(db.select(Seller)).all()
        assert [r.store_name for r in rows] == ["Nuevo nombre de tienda"]


@pytest.mark.parametrize("override", [{"store_name": ""}, {"store_name": "ab"}, {"store_name": "x" * 81},
                                      {"store_name": "Tienda\x00mala"}, {"description": "y" * 301}])
def test_store_rejects_invalid_data(as_alice, app, override):
    assert _save(as_alice, **override).status_code == 200
    with app.app_context():
        assert db.session.scalars(db.select(Seller)).all() == []


def test_store_name_is_escaped(as_alice, client):
    _save(as_alice, store_name="<script>alert(1)</script>")
    page = client.get("/items/PROD-001").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_store_requires_login_and_a_user_account(client, as_admin):
    assert as_admin.get("/store/edit").status_code == 403


def test_store_requires_login(client):
    response = client.get("/store/edit")
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]


def test_mass_assignment_is_ignored(as_alice, app):
    _save(as_alice, seller_id="SEL-999999", user_id="x")
    with app.app_context():
        assert [r.seller_id for r in db.session.scalars(db.select(Seller)).all()] == ["SEL-000001"]
