"""Control de acceso: rutas sin sesión, roles, IDOR, escalada y métodos HTTP."""
import pytest

from Core.Extensions import db
from Models import User

from .conftest import IDS, get_csrf, login, post_form

PROTECTED_GET = [
    "/dashboard", "/profile", "/auth/password",
    "/items/mine", "/items/new",
    "/items/PROD-001/edit", "/items/PROD-001/block",
    "/users/", "/users/new", f"/users/{IDS['alice']}", f"/users/{IDS['alice']}/edit",
]
PROTECTED_POST = [
    "/auth/logout", "/items/new", "/items/PROD-001/edit", "/items/PROD-001/delete",
    "/items/PROD-001/block", "/items/PROD-001/unblock",
    "/users/new", f"/users/{IDS['alice']}/edit", f"/users/{IDS['alice']}/delete",
]


# Navegación pública (como Mercado Libre): se puede ver todo el catálogo sin cuenta.
PUBLIC_GET = ["/", "/items/", "/items/?q=laptop", "/items/?department=electronics&sort=price_asc",
              "/items/PROD-001"]


@pytest.mark.parametrize("path", PUBLIC_GET)
def test_catalog_is_public_without_session(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "/auth/login" not in response.headers.get("Location", "")


@pytest.mark.parametrize("path", PROTECTED_GET)
def test_protected_get_without_session_redirects_to_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


@pytest.mark.parametrize("path", PROTECTED_POST)
def test_protected_post_without_session_never_executes(client, app, table, path):
    token = get_csrf(client, "/auth/login")
    response = client.post(path, data={"csrf_token": token, "name": "x", "reason": "motivo largo"})
    assert response.status_code in (302, 400, 401, 403)
    if response.status_code == 302:
        assert "/auth/login" in response.headers["Location"]
    assert table.items["PROD-001"]["status"] == "ACTIVE"
    with app.app_context():
        assert db.session.get(User, IDS["alice"]).status == "active"


@pytest.mark.parametrize("path", ["/users/", "/users/new", f"/users/{IDS['bob']}", f"/users/{IDS['bob']}/edit"])
def test_regular_user_cannot_access_user_management(as_alice, path):
    assert as_alice.get(path).status_code == 403


def test_regular_user_cannot_escalate_own_role(as_alice, app):
    token = get_csrf(as_alice, "/dashboard")
    response = as_alice.post(f"/users/{IDS['alice']}/edit", data={
        "csrf_token": token, "first_name": "Alice", "last_name": "Prueba",
        "email": "alice@marketplace.mx", "role": "admin", "status": "active",
    })
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(User, IDS["alice"]).role == "user"


def test_regular_user_cannot_delete_other_users(as_alice, app):
    token = get_csrf(as_alice, "/dashboard")
    response = as_alice.post(f"/users/{IDS['bob']}/delete", data={"csrf_token": token})
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(User, IDS["bob"]).status == "active"


def test_regular_user_cannot_block_products(as_alice, table):
    token = get_csrf(as_alice, "/dashboard")
    response = as_alice.post("/items/PROD-002/block", data={"csrf_token": token, "reason": "Quiero bloquearlo"})
    assert response.status_code == 403
    assert table.items["PROD-002"]["status"] == "ACTIVE"


# ------------------------------------------------------------------ IDOR
def test_idor_edit_other_users_product_get(as_bob):
    assert as_bob.get("/items/PROD-001/edit").status_code == 403


def test_idor_edit_other_users_product_post(as_bob, table):
    token = get_csrf(as_bob, "/items/new")
    response = as_bob.post("/items/PROD-001/edit", data={
        "csrf_token": token, "name": "Hackeado", "category": "computers",
        "description": "Descripcion de prueba del producto", "price": "1.00", "stock": "0", "condition": "NEW", "version": "1",
    })
    assert response.status_code == 403
    assert table.items["PROD-001"]["name"] == "Laptop HP Victus"
    assert table.items["PROD-001"]["seller_id"] == "SEL-000001"


def test_idor_delete_other_users_product(as_bob, table):
    token = get_csrf(as_bob, "/items/new")
    response = as_bob.post("/items/PROD-001/delete", data={"csrf_token": token})
    assert response.status_code == 403
    assert "PROD-001" in table.items


def test_cannot_steal_product_by_sending_seller_id(as_bob, table):
    response = post_form(as_bob, "/items/PROD-002/edit", {
        "name": "Mouse Logitech", "category": "computer-accessories", "price": "500.00",
        "description": "Descripcion de prueba del producto", "stock": "25", "condition": "NEW", "version": "1",
        "seller_id": "SEL-000001", "status": "BLOCKED", "product_id": "PROD-001",
    })
    assert response.status_code == 302
    assert table.items["PROD-002"]["seller_id"] == "SEL-000002"
    assert table.items["PROD-002"]["status"] == "ACTIVE"
    assert table.items["PROD-001"]["name"] == "Laptop HP Victus"


def test_admin_has_no_store_and_cannot_create_products(as_admin):
    assert as_admin.get("/items/new").status_code == 403
    assert as_admin.get("/items/mine").status_code == 403


# ------------------------------------------------------------------ métodos HTTP
@pytest.mark.parametrize("path", ["/items/PROD-001/delete", "/items/PROD-001/unblock",
                                  f"/users/{IDS['bob']}/delete", "/auth/logout"])
def test_state_changing_routes_reject_get(as_admin, path):
    assert as_admin.get(path).status_code == 405


def test_unsupported_methods_rejected(as_alice):
    assert as_alice.put("/items/PROD-001/edit").status_code == 405
    assert as_alice.delete("/items/PROD-001").status_code == 405


# ------------------------------------------------------------------ sesión y roles
def test_tampered_session_cookie_is_rejected(as_alice, app):
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    value = as_alice.get_cookie(cookie_name).value
    as_alice.set_cookie(cookie_name, value[:-4] + ("AAAA" if not value.endswith("AAAA") else "BBBB"))
    response = as_alice.get("/dashboard")
    assert response.status_code == 302


def test_suspending_user_kills_existing_session(client, app):
    login(client, "alice")
    assert client.get("/dashboard").status_code == 200
    with app.app_context():
        user = db.session.get(User, IDS["alice"])
        user.status = "suspended"
        db.session.commit()
    assert client.get("/dashboard").status_code == 302


def test_products_api_requires_token_even_with_the_url(app, table):
    """Aunque el atacante conozca la URL del API Gateway, sin el token no puede borrar."""
    gateway = app.extensions["fake_gateway"]
    url = app.config["PRODUCTS_API_URL"] + "/products/PROD-001"
    assert gateway.request("DELETE", url, headers={}, timeout=5).status_code == 401
    forged = {"x-mkt-token": "adivinado" * 5, "x-mkt-actor-role": "admin"}
    assert gateway.request("DELETE", url, headers=forged, timeout=5).status_code == 403
    assert "PROD-001" in table.items
