"""CRUD de productos, validación, búsqueda e inyecciones."""
import pytest

from Core.Extensions import db
from Models import AdminAction

from .conftest import login, post_form

VALID = {"name": "Teclado inalambrico compacto", "category": "computer-accessories",
         "description": "Descripcion de prueba del producto", "price": "749.00", "stock": "15", "condition": "NEW"}


def _create(client, **overrides):
    data = dict(VALID)
    data.update(overrides)
    return post_form(client, "/items/new", data)


def _product_by_name(table, name):
    matches = [item for item in table.items.values() if item["name"] == name]
    return matches[0] if matches else None


# ------------------------------------------------------------------ flujos felices
def test_create_product(as_alice, table):
    response = _create(as_alice)
    assert response.status_code == 302
    product = _product_by_name(table, VALID["name"])
    assert product is not None
    assert product["seller_id"] == "SEL-000001"
    assert str(product["price"]) == "749.00"
    assert product["listed_category"] == "computer-accessories"
    page = as_alice.get(response.headers["Location"]).get_data(as_text=True)
    assert VALID["name"] in page


def test_catalog_lists_active_products(as_alice):
    body = as_alice.get("/items/").get_data(as_text=True)
    assert "Laptop HP Victus" in body and "Mouse Logitech" in body


def test_edit_own_product(as_alice, table):
    response = post_form(as_alice, "/items/PROD-001/edit", {
        "name": "Laptop HP Victus 16", "category": "computers", "price": "17999.50",
        "description": "Descripcion de prueba del producto", "stock": "4", "condition": "REFURBISHED", "version": "1",
    })
    assert response.status_code == 302
    product = table.items["PROD-001"]
    assert product["name"] == "Laptop HP Victus 16"
    assert str(product["price"]) == "17999.50"
    assert product["stock"] == 4
    assert product["version"] == 2


def test_edit_with_stale_version_is_rejected(as_alice, table):
    response = post_form(as_alice, "/items/PROD-001/edit", {
        "name": "Cambio viejo", "category": "computers", "price": "1.00",
        "description": "Descripcion de prueba del producto", "stock": "1", "condition": "NEW", "version": "99",
    })
    assert response.status_code == 302
    assert table.items["PROD-001"]["name"] == "Laptop HP Victus"


def test_delete_own_product(as_alice, table):
    response = post_form(as_alice, "/items/PROD-001/delete", {}, token_path="/items/PROD-001")
    assert response.status_code == 302
    assert "PROD-001" not in table.items


def test_admin_can_block_unblock_and_delete_as_moderation(as_admin, app, table):
    response = post_form(as_admin, "/items/PROD-002/block", {"reason": "Producto engañoso"})
    assert response.status_code == 302
    assert table.items["PROD-002"]["status"] == "BLOCKED"
    assert "listed_category" not in table.items["PROD-002"]
    response = post_form(as_admin, "/items/PROD-002/unblock", {}, token_path="/items/PROD-002")
    assert response.status_code == 302
    response = post_form(as_admin, "/items/PROD-002/delete", {}, token_path="/items/PROD-002")
    assert response.status_code == 302
    assert "PROD-002" not in table.items
    with app.app_context():
        actions = {a.action for a in db.session.query(AdminAction).all()}
        assert {"block_product", "unblock_product", "delete_product"} <= actions


def test_blocked_product_hidden_from_others(as_admin, app):
    post_form(as_admin, "/items/PROD-002/block", {"reason": "Revisión de moderación"})
    other = app.test_client()
    login(other, "alice")
    assert other.get("/items/PROD-002").status_code == 404
    assert "Mouse Logitech" not in other.get("/items/").get_data(as_text=True)
    owner = app.test_client()
    login(owner, "bob")
    assert owner.get("/items/PROD-002").status_code == 200


# ------------------------------------------------------------------ validación
@pytest.mark.parametrize("overrides", [
    {"name": ""},
    {"name": "ab"},
    {"name": "x" * 121},
    {"name": "Mouse\x00nulo"},
    {"name": "Linea\r\nInyectada"},
    {"price": "-1"},
    {"price": "0"},
    {"price": "abc"},
    {"price": "NaN"},
    {"price": "Infinity"},
    {"price": "1e309"},
    {"price": "10.999"},
    {"price": "99999999"},
    {"stock": "-1"},
    {"stock": "1.5"},
    {"stock": "abc"},
    {"stock": "100001"},
    {"category": "../../etc/passwd"},
    {"category": "no-existe"},
    {"condition": "ROBADO"},
])
def test_create_product_rejects_invalid_input(as_alice, table, overrides):
    response = _create(as_alice, **overrides)
    assert response.status_code == 200
    assert len(table.items) == 2


def test_unicode_product_name_is_accepted(as_alice, table):
    assert _create(as_alice, name="Silla ergonómica Ñandú 🪑").status_code == 302
    assert _product_by_name(table, "Silla ergonómica Ñandú 🪑") is not None


# ------------------------------------------------------------------ XSS / SSTI
@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "\"><svg onload=alert(1)>",
])
def test_stored_xss_is_escaped(as_alice, payload):
    assert _create(as_alice, name=payload).status_code == 302
    for path in ["/items/", "/items/mine", "/dashboard"]:
        body = as_alice.get(path).get_data(as_text=True)
        assert payload not in body
        assert "&lt;" in body


def test_ssti_payload_is_not_evaluated(as_alice):
    _create(as_alice, name="{{7*7}} {{config}}")
    body = as_alice.get("/items/?q=7").get_data(as_text=True)
    assert "{{7*7}}" in body
    assert "SECRET_KEY" not in body


def test_reflected_xss_in_search_is_escaped(as_alice):
    payload = "<script>alert(1)</script>"
    body = as_alice.get("/items/", query_string={"q": payload}).get_data(as_text=True)
    assert payload not in body
    assert "&lt;script&gt;" in body


# ------------------------------------------------------------------ búsqueda
def test_search_by_name_and_sku(as_alice):
    body = as_alice.get("/items/", query_string={"q": "laptop"}).get_data(as_text=True)
    assert "Laptop HP Victus" in body and "Mouse Logitech" not in body
    # Se busca por el SKU público del vendedor, no por el product_id interno.
    body = as_alice.get("/items/", query_string={"q": "mou-log-002"}).get_data(as_text=True)
    assert "Mouse Logitech" in body and "Laptop HP Victus" not in body


def test_search_does_not_match_internal_product_id(as_alice):
    # El product_id interno (PROD-002) NO debe funcionar como búsqueda pública.
    body = as_alice.get("/items/", query_string={"q": "prod-002"}).get_data(as_text=True)
    assert "Mouse Logitech" not in body


@pytest.mark.parametrize("payload", ["' OR '1'='1", "' OR 1=1 --", "'; DROP TABLE products;--",
                                     "\" OR \"\"=\"", "laptop' UNION SELECT password_hash FROM users--"])
def test_search_sql_injection(as_alice, table, payload):
    response = as_alice.get("/items/", query_string={"q": payload})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Mouse Logitech" not in body
    assert "$argon2" not in body
    assert len(table.items) == 2


@pytest.mark.parametrize("wildcard", ["%", "_", "%%", "\\"])
def test_search_like_wildcards_are_literal(as_alice, wildcard):
    body = as_alice.get("/items/", query_string={"q": wildcard}).get_data(as_text=True)
    assert "Laptop HP Victus" not in body and "Mouse Logitech" not in body


def test_search_too_long_or_control_chars(as_alice):
    for q in ["a" * 65, "lap\x00top", "lap\ntop"]:
        response = as_alice.get("/items/", query_string={"q": q})
        assert response.status_code == 200
        assert "Laptop HP Victus" not in response.get_data(as_text=True)


def test_search_invalid_category_and_page(as_alice):
    assert as_alice.get("/items/?category=../../x").status_code == 200
    assert as_alice.get("/items/?page=-1").status_code == 200
    assert as_alice.get("/items/?page=abc").status_code == 200
    assert as_alice.get("/items/?page=99999999999999999999").status_code == 200


# ------------------------------------------------------------------ path traversal
@pytest.mark.parametrize("path", [
    "/items/..%2F..%2Fetc%2Fpasswd",
    "/items/PROD-001%2F..%2F..%2Fapp",
    "/items/../../etc/passwd",
    "/items/PROD-001'%20OR%20'1'='1",
    "/static/..%2F..%2Fconfig.py",
    "/static/../Core/Config.py",
])
def test_path_traversal_returns_404(as_alice, path):
    response = as_alice.get(path)
    assert response.status_code == 404
    assert "SECRET_KEY" not in response.get_data(as_text=True)


def test_api_outage_shows_generic_503(as_alice, app):
    app.extensions["fake_gateway"].down = True
    response = as_alice.get("/items/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    assert "execute-api" not in body and "Traceback" not in body


def test_api_token_never_reaches_the_browser(as_alice, app):
    token = app.config["PRODUCTS_API_TOKEN"]
    for path in ["/items/", "/items/PROD-001", "/items/new", "/dashboard"]:
        response = as_alice.get(path)
        assert token not in response.get_data(as_text=True)
        assert token not in str(response.headers)


# ------------------------------------------------------------------ filtros, orden y portada (rediseño)
def test_filter_by_department_and_availability(as_alice):
    body = as_alice.get("/items/", query_string={"department": "home-office"}).get_data(as_text=True)
    assert "Laptop HP Victus" not in body and "Mouse Logitech" not in body
    body = as_alice.get("/items/", query_string={"department": "electronics"}).get_data(as_text=True)
    assert "Laptop HP Victus" in body and "Mouse Logitech" in body
    body = as_alice.get("/items/", query_string={"availability": "in_stock"}).get_data(as_text=True)
    assert "Laptop HP Victus" in body
    body = as_alice.get("/items/", query_string={"availability": "sold_out"}).get_data(as_text=True)
    assert "Laptop HP Victus" not in body


def test_sort_by_price(as_alice):
    body = as_alice.get("/items/", query_string={"sort": "price_asc"}).get_data(as_text=True)
    assert body.index("Mouse Logitech") < body.index("Laptop HP Victus")
    body = as_alice.get("/items/", query_string={"sort": "price_desc"}).get_data(as_text=True)
    assert body.index("Laptop HP Victus") < body.index("Mouse Logitech")


@pytest.mark.parametrize("query", [{"sort": "'; DROP"}, {"department": "<script>"}, {"availability": "todo"},
                                   {"category": "../../x"}])
def test_filters_outside_whitelist_return_nothing(as_alice, query):
    response = as_alice.get("/items/", query_string=query)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Laptop HP Victus" not in body and "<script>" not in body


def test_detail_shows_related_and_public_seller_name(as_alice):
    _create(as_alice, name="Laptop Lenovo IdeaPad", category="computers")
    body = as_alice.get("/items/PROD-001").get_data(as_text=True)
    assert "Laptop Lenovo IdeaPad" in body          # relacionado (misma categoría)
    assert "Vendido por Alice P." in body
    assert "alice@marketplace.mx" not in body       # nunca se expone el correo del vendedor


def test_home_shows_search_departments_and_latest(as_alice):
    body = as_alice.get("/dashboard").get_data(as_text=True)
    assert "¿Qué buscas hoy, Alice?" in body
    assert "Compra por departamento" in body and "Recién publicados" in body
    assert "Laptop HP Victus" in body and "Mouse Logitech" in body
    assert "SEL-000001" in body                      # código de su tienda


def test_admin_home_is_the_admin_panel(as_admin):
    body = as_admin.get("/dashboard").get_data(as_text=True)
    assert "Panel de administración" in body and "Últimos accesos fallidos" in body
