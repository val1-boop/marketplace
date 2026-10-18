"""Navegación pública (sin cuenta, como Mercado Libre) y archivos estáticos de las vistas.

Lo público solo LEE: ver portada, catálogo, búsqueda y fichas. Todo lo que cambia datos
(publicar, editar, borrar, moderar, administrar usuarios) sigue exigiendo sesión.
"""
import pytest

from .conftest import EMAILS, login, post_form


def test_public_home_without_session(client):
    body = client.get("/").get_data(as_text=True)
    assert "¿Qué buscas hoy?" in body
    assert "Laptop HP Victus" in body and "Mouse Logitech" in body
    assert "Iniciar sesión" in body and "Crear cuenta" in body
    assert "Tu tienda" not in body and "Mis productos" not in body


def test_public_detail_shows_product_but_no_owner_actions(client):
    body = client.get("/items/PROD-001").get_data(as_text=True)
    assert "Laptop HP Victus" in body and "18,500.00" in body
    assert "Vendido por Alice P." in body
    assert "Editar producto" not in body and "Bloquear" not in body
    assert "/items/PROD-001/delete" not in body
    for email in EMAILS.values():          # nunca se expone el correo de nadie
        assert email not in body


def test_public_never_sees_blocked_products(client, table):
    table.items["PROD-002"]["status"] = "BLOCKED"
    table.items["PROD-002"].pop("listed_category", None)
    assert client.get("/items/PROD-002").status_code == 404
    assert "Mouse Logitech" not in client.get("/items/").get_data(as_text=True)
    assert "Mouse Logitech" not in client.get("/").get_data(as_text=True)


def test_public_search_and_filters_work(client):
    body = client.get("/items/", query_string={"q": "laptop"}).get_data(as_text=True)
    assert "Laptop HP Victus" in body and "Mouse Logitech" not in body
    body = client.get("/items/", query_string={"category": "computer-accessories"}).get_data(as_text=True)
    assert "Mouse Logitech" in body and "Laptop HP Victus" not in body


@pytest.mark.parametrize("payload", ["<script>alert(1)</script>", "{{7*7}}", "' OR 1=1 --"])
def test_public_search_is_escaped_and_safe(client, payload):
    response = client.get("/items/", query_string={"q": payload})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in body
    assert ">49<" not in body
    assert "Laptop HP Victus" not in body


def test_sell_button_asks_for_login_and_returns_to_the_form(client):
    response = client.get("/items/new")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"] and "next=" in response.headers["Location"]
    response = login(client, "alice", next_url="/items/new")
    assert response.headers["Location"].endswith("/items/new")
    assert client.get("/items/new").status_code == 200


def test_anonymous_cannot_write_even_with_a_valid_csrf_token(client, table):
    response = post_form(client, "/items/PROD-001/delete", {}, token_path="/auth/login")
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]
    assert "PROD-001" in table.items


def test_public_pages_never_leak_the_api_token(client, app):
    token = app.config["PRODUCTS_API_TOKEN"]
    for path in ["/", "/items/", "/items/PROD-001"]:
        response = client.get(path)
        assert token not in response.get_data(as_text=True)
        assert token not in str(response.headers)


def test_public_catalog_is_rate_limited(client, app):
    app.config["SEARCH_RATE_LIMIT"] = "3 per minute"
    codes = [client.get("/items/").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]


def test_logged_user_home_still_shows_greeting_and_shop(as_alice):
    body = as_alice.get("/").get_data(as_text=True)
    assert "¿Qué buscas hoy, Alice?" in body and "Tu tienda" in body


# ---------------------------------------------------------------- caché del listado
def test_product_list_cache_reduces_api_calls_and_clears_on_write(as_alice, app, table):
    app.config["PRODUCT_LIST_CACHE_SECONDS"] = 60
    api = app.extensions["products_api"]
    calls = {"n": 0}
    original = api.list_products

    def counting(seller_id=None):
        if seller_id is None:
            calls["n"] += 1
        return original(seller_id=seller_id)

    api.list_products = counting
    for _ in range(3):
        as_alice.get("/items/")
    assert calls["n"] == 1                         # tres visitas, una sola llamada al API
    post_form(as_alice, "/items/new", {"name": "Monitor 24 pulgadas", "category": "monitors",
                                       "description": "Descripcion de prueba del producto", "price": "2999.00", "stock": "5", "condition": "NEW"})
    body = as_alice.get("/items/").get_data(as_text=True)
    assert "Monitor 24 pulgadas" in body           # la escritura vació la caché
    assert calls["n"] == 2


# ---------------------------------------------------------------- archivos de las vistas
@pytest.mark.parametrize("path,ctype", [
    ("/assets/SharedViews/CSS/Base.css", "text/css"),
    ("/assets/ProductViews/CSS/Product.css", "text/css"),
    ("/assets/SharedViews/JS/App.js", "text/javascript"),
    ("/assets/SharedViews/CSS/Fonts/Archivo-Variable.ttf", "font/ttf"),
])
def test_view_assets_are_served(client, path, ctype):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(ctype)


@pytest.mark.parametrize("path", [
    "/assets/SharedViews/PY/SharedForms.py",           # código Python: nunca se publica
    "/assets/ProductViews/HTML/Catalog.html",          # plantillas: tampoco
    "/assets/SharedViews/CSS/../PY/SharedForms.py",
    "/assets/SharedViews/CSS/..%2F..%2F..%2FCore%2FConfig.py",
    "/assets/SharedViews/CSS/%2e%2e/%2e%2e/%2e%2e/.env",
    "/assets/Core/CSS/x.css",                          # vista fuera de la lista blanca
    "/assets/SharedViews/Utils/Assets.py",
    "/assets/SharedViews/CSS/Fonts/OFL-Archivo.txt",   # extensión fuera de la lista blanca
    "/assets/SharedViews/CSS/Nada.css",
])
def test_view_assets_never_expose_code_or_other_files(client, path):
    response = client.get(path)
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert "SECRET_KEY" not in body and "import " not in body
