"""Flujos de compra en Flask: carrito, favoritos, direcciones, compra, estados, ventas y reseñas.

Todo pasa por el API Gateway simulado que ejecuta las Lambdas REALES. Además del flujo feliz
se prueban los ataques típicos: sin sesión, CSRF, IDOR (dirección o pedido ajeno), precio
manipulado, cantidades fuera de rango, saltos de estado, reseña sin compra, XSS y open redirect.
"""
from decimal import Decimal

import pytest

from Core.Extensions import db
from Models import Address, User, utcnow
from Security import hash_password, normalize_email

from .conftest import IDS, get_csrf, login

CAROL_ID = "00000000-0000-4000-8000-000000000004"
CAROL_PASSWORD = "Carol-Clave-Segura-2026!"
ADDRESS_FORM = {"label": "Casa", "recipient_name": "Bob Prueba", "phone": "5512345678",
                "line1": "Av. Reforma 100", "line2": "Depto 4", "city": "Cuauhtémoc",
                "state": "Ciudad de México", "postal_code": "06600"}


def post(client, path, data=None, token_path="/auth/change-password"):
    payload = dict(data or {})
    payload["csrf_token"] = get_csrf(client, token_path)
    return client.post(path, data=payload)


def products(app):
    return app.extensions["fake_gateway"].dynamo.tables["Products"].items


def add_address(client, **overrides):
    data = dict(ADDRESS_FORM, **overrides)
    return post(client, "/addresses/new", data)


def address_ids(app, user_id):
    with app.app_context():
        return [a.id for a in db.session.scalars(db.select(Address).where(Address.user_id == user_id)).all()]


def buy(client, app, product_id="PROD-001", quantity=1):
    """Bob compra un producto: dirección + carrito + confirmar. Devuelve el ID del pedido."""
    if not address_ids(app, IDS["bob"]):
        assert add_address(client).status_code == 302
    assert post(client, f"/cart/add/{product_id}", {"quantity": str(quantity)}).status_code == 302
    response = post(client, "/checkout", {"address_id": str(address_ids(app, IDS["bob"])[0])}, "/checkout")
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    location = response.headers["Location"]
    assert "/orders/" in location
    return location.rstrip("/").rsplit("/", 1)[-1]


def change(client, order_id, action, reason=None):
    data = {"action": action}
    if reason:
        data["reason"] = reason
    return post(client, f"/orders/{order_id}/status", data, f"/orders/{order_id}")


@pytest.fixture
def carol(app):
    with app.app_context():
        db.session.add(User(
            id=CAROL_ID, email="carol@marketplace.mx", email_normalized=normalize_email("carol@marketplace.mx"),
            first_name="Carol", last_name="Prueba", password_hash=hash_password(CAROL_PASSWORD), role="user",
            status="active", seller_id="SEL-000003", terms_version="2026-10", privacy_version="2026-10",
            terms_accepted_at=utcnow(),
        ))
        db.session.commit()


# ---------------------------------------------------------------- acceso
@pytest.mark.parametrize("path", ["/cart/", "/favorites/", "/orders/", "/sales/", "/checkout", "/addresses/",
                                  "/addresses/new"])
def test_shop_pages_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


@pytest.mark.parametrize("path", ["/cart/add/PROD-001", "/favorites/add/PROD-001", "/items/PROD-001/reviews"])
def test_shop_posts_require_login(client, app, path):
    response = client.post(path, data={"quantity": "1", "rating": "5", "comment": "x" * 20})
    assert response.status_code in (302, 400)  # a iniciar sesión (o CSRF), nunca 200
    gateway = app.extensions["fake_gateway"]
    assert not gateway.dynamo.tables["Marketplace"].items and not gateway.dynamo.tables["Community"].items


@pytest.mark.parametrize("path", ["/cart/", "/favorites/", "/orders/", "/sales/", "/checkout", "/addresses/"])
def test_admin_does_not_shop(as_admin, path):
    assert as_admin.get(path).status_code == 403


def test_anonymous_sees_login_links_instead_of_buy_forms(client):
    body = client.get("/items/PROD-001").get_data(as_text=True)
    assert "Agregar al carrito" in body and "Comprar ahora" in body
    assert "/cart/add/PROD-001" not in body
    assert "/auth/login?next=" in body


# ---------------------------------------------------------------- carrito
def test_add_to_cart_and_view(as_bob, app):
    response = post(as_bob, "/cart/add/PROD-001", {"quantity": "2"})
    assert response.status_code == 302
    body = as_bob.get("/cart/").get_data(as_text=True)
    assert "Laptop HP Victus" in body and "37,000.00" in body
    assert 'class="count-badge">2<' in as_bob.get("/").get_data(as_text=True)


def test_cart_ignores_price_sent_by_browser(as_bob, app):
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1", "price": "1.00", "unit_price": "1.00"})
    body = as_bob.get("/cart/").get_data(as_text=True)
    assert "18,500.00" in body and "$1.00" not in body


@pytest.mark.parametrize("quantity", ["0", "11", "-1", "abc", "1.5", ""])
def test_cart_rejects_bad_quantities(as_bob, app, quantity):
    post(as_bob, "/cart/add/PROD-001", {"quantity": quantity})
    assert "Tu carrito está vacío" in as_bob.get("/cart/").get_data(as_text=True)


def test_cannot_buy_own_product(as_alice):
    response = post(as_alice, "/cart/add/PROD-001", {"quantity": "1"})
    assert response.status_code == 302
    assert "Tu carrito está vacío" in as_alice.get("/cart/").get_data(as_text=True)


def test_cart_more_than_stock_is_rejected(as_bob):
    post(as_bob, "/cart/add/PROD-001", {"quantity": "8"})  # solo hay 7
    assert "Tu carrito está vacío" in as_bob.get("/cart/").get_data(as_text=True)


@pytest.mark.parametrize("pid", ["..%2F..%2Forders", "PROD-001%3Fx%3D1", "prod-001", "PROD-1"])
def test_cart_rejects_invalid_product_ids(as_bob, pid):
    response = post(as_bob, f"/cart/add/{pid}", {"quantity": "1"})
    assert response.status_code == 404


def test_cart_actions_require_csrf(as_bob):
    assert as_bob.post("/cart/add/PROD-001", data={"quantity": "1"}).status_code == 400
    assert as_bob.post("/cart/remove/PROD-001").status_code == 400


def test_cart_update_and_remove(as_bob):
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1"})
    post(as_bob, "/cart/update/PROD-001", {"quantity": "3"}, "/cart/")
    assert "55,500.00" in as_bob.get("/cart/").get_data(as_text=True)
    post(as_bob, "/cart/remove/PROD-001", {}, "/cart/")
    assert "Tu carrito está vacío" in as_bob.get("/cart/").get_data(as_text=True)


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com/x", "/\\evil.com", "javascript:alert(1)"])
def test_cart_next_is_not_an_open_redirect(as_bob, target):
    response = post(as_bob, "/cart/add/PROD-001", {"quantity": "1", "next": target})
    assert response.headers["Location"].endswith("/items/PROD-001")


def test_buy_now_goes_to_checkout(as_bob):
    response = post(as_bob, "/cart/buy/PROD-001", {"quantity": "1"})
    assert response.headers["Location"].endswith("/checkout")


def test_buy_now_own_product_stays_on_detail(as_bob):
    response = post(as_bob, "/cart/buy/PROD-002", {"quantity": "1"})  # PROD-002 es de Bob
    assert response.headers["Location"].endswith("/items/PROD-002")


# ---------------------------------------------------------------- favoritos
def test_favorites_add_list_remove(as_bob):
    post(as_bob, "/favorites/add/PROD-001", {"next": "/items/"})
    body = as_bob.get("/favorites/").get_data(as_text=True)
    assert "Laptop HP Victus" in body
    assert 'aria-pressed="true"' in as_bob.get("/items/PROD-001").get_data(as_text=True)
    post(as_bob, "/favorites/remove/PROD-001", {})
    assert "Aún no tienes favoritos" in as_bob.get("/favorites/").get_data(as_text=True)


def test_favorite_of_missing_product_is_404(as_bob):
    assert post(as_bob, "/favorites/add/PROD-999", {}).status_code == 404


# ---------------------------------------------------------------- direcciones
def test_address_crud_and_single_default(as_bob, app):
    assert add_address(as_bob).status_code == 302
    assert add_address(as_bob, label="Trabajo", make_default="y").status_code == 302
    with app.app_context():
        rows = db.session.scalars(db.select(Address).where(Address.user_id == IDS["bob"])).all()
        assert sorted((r.label, r.is_default) for r in rows) == [("Casa", False), ("Trabajo", True)]
    body = as_bob.get("/addresses/").get_data(as_text=True)
    assert "Casa" in body and "Trabajo" in body and "Predeterminada" in body


@pytest.mark.parametrize("field,value", [("phone", "55-1234"), ("postal_code", "6600"), ("state", "Texas"),
                                         ("recipient_name", "<script>x</script>"), ("line1", "a\u0000b")])
def test_address_validation(as_bob, app, field, value):
    response = add_address(as_bob, **{field: value})
    assert response.status_code == 200
    assert address_ids(app, IDS["bob"]) == []


def test_address_mass_assignment_is_ignored(as_bob, app):
    add_address(as_bob, user_id=IDS["alice"], is_active="0", country="US", id="999")
    with app.app_context():
        row = db.session.scalars(db.select(Address)).one()
        assert row.user_id == IDS["bob"] and row.is_active and row.country == "MX" and row.id != 999


def test_address_idor_is_404(client, app):
    login(client, "alice")
    add_address(client, recipient_name="Alice Prueba")
    alice_address = address_ids(app, IDS["alice"])[0]
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "bob")
    assert client.get(f"/addresses/{alice_address}/edit").status_code == 404
    assert post(client, f"/addresses/{alice_address}/delete", {}).status_code == 404
    assert post(client, f"/addresses/{alice_address}/default", {}).status_code == 404
    with app.app_context():
        assert db.session.get(Address, alice_address).is_active


# ---------------------------------------------------------------- compra
def test_checkout_without_address_asks_for_one(as_bob):
    post(as_bob, "/cart/add/PROD-001", {"quantity": "1"})
    body = as_bob.get("/checkout").get_data(as_text=True)
    assert "Necesitas una dirección de envío" in body


def test_checkout_with_someone_elses_address_fails(client, app):
    login(client, "alice")
    add_address(client, recipient_name="Alice Prueba")
    alice_address = address_ids(app, IDS["alice"])[0]
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "bob")
    add_address(client)
    post(client, "/cart/add/PROD-001", {"quantity": "1"})
    response = post(client, "/checkout", {"address_id": str(alice_address)}, "/checkout")
    assert response.status_code == 200  # opción no válida: no se crea nada
    assert products(app)["PROD-001"]["stock"] == 7


def test_checkout_creates_order_and_updates_stock(as_bob, app):
    order_id = buy(as_bob, app, quantity=2)
    assert products(app)["PROD-001"]["stock"] == 5
    body = as_bob.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "Confirmado" in body and "Laptop HP Victus" in body and "Av. Reforma 100" in body
    assert "Llega entre el" in body
    assert "Tu carrito está vacío" in as_bob.get("/cart/").get_data(as_text=True)
    assert "Laptop HP Victus" in as_bob.get("/orders/").get_data(as_text=True)


def test_sales_page_shows_order_to_seller(as_bob, app, client):
    buy(as_bob, app)
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "alice")
    body = client.get("/sales/").get_data(as_text=True)
    assert "Laptop HP Victus" in body and "Preparar" in body


def test_order_of_someone_else_is_404(as_bob, app, client, carol):
    order_id = buy(as_bob, app)
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, email="carol@marketplace.mx", password=CAROL_PASSWORD)
    assert client.get(f"/orders/{order_id}").status_code == 404
    assert change(client, order_id, "cancel").status_code in (400, 404)
    assert client.get("/orders/../admin").status_code == 404


def test_full_status_flow_and_permissions(as_bob, app, client):
    order_id = buy(as_bob, app)
    # El comprador no puede preparar ni enviar.
    assert change(as_bob, order_id, "prepare").status_code == 403
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "alice")
    assert change(client, order_id, "deliver").status_code == 403  # el vendedor no confirma la entrega
    change(client, order_id, "ship")  # salto de estado: 409, se avisa y no cambia
    assert "Confirmado" in client.get(f"/orders/{order_id}").get_data(as_text=True)
    change(client, order_id, "prepare")
    change(client, order_id, "ship")
    assert "Enviado" in client.get(f"/orders/{order_id}").get_data(as_text=True)
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "bob")
    change(client, order_id, "deliver")
    body = client.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "Entregado" in body and "Opinar sobre este producto" in body


def test_invalid_action_is_400(as_bob, app):
    order_id = buy(as_bob, app)
    assert change(as_bob, order_id, "refund").status_code == 400


def test_buyer_cancel_restocks(as_bob, app):
    order_id = buy(as_bob, app, quantity=3)
    assert products(app)["PROD-001"]["stock"] == 4
    change(as_bob, order_id, "cancel", "Me equivoqué de modelo")
    assert products(app)["PROD-001"]["stock"] == 7
    assert "Cancelado" in as_bob.get(f"/orders/{order_id}").get_data(as_text=True)


def test_admin_can_view_and_cancel_order(as_bob, app, client):
    order_id = buy(as_bob, app)
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "admin")
    assert "Vista de administración" in client.get(f"/orders/{order_id}").get_data(as_text=True)
    change(client, order_id, "cancel")
    assert products(app)["PROD-001"]["stock"] == 7


# ---------------------------------------------------------------- reseñas
def _deliver(as_bob, app, client):
    order_id = buy(as_bob, app)
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "alice")
    change(client, order_id, "prepare")
    change(client, order_id, "ship")
    client.post("/auth/logout", data={"csrf_token": get_csrf(client, "/auth/change-password")})
    login(client, "bob")
    change(client, order_id, "deliver")
    return order_id


def review(client, rating="5", comment="Excelente laptop, llegó rápido y bien empacada."):
    return post(client, "/items/PROD-001/reviews", {"rating": rating, "comment": comment}, "/items/PROD-001")


def test_review_requires_delivered_purchase(as_bob, app):
    assert "Podrás opinar cuando recibas" in as_bob.get("/items/PROD-001").get_data(as_text=True)
    review(as_bob)
    assert "rating_count" not in products(app)["PROD-001"] or products(app)["PROD-001"]["rating_count"] == 0


def test_review_after_delivery_updates_average(as_bob, app, client):
    _deliver(as_bob, app, client)
    assert "Publicar opinión" in client.get("/items/PROD-001").get_data(as_text=True)
    review(client, "4")
    body = client.get("/items/PROD-001").get_data(as_text=True)
    assert "Bob P." in body and "Compra verificada" in body and "4.0" in body
    assert products(app)["PROD-001"]["rating_count"] == 1
    review(client, "1", "Quiero volver a opinar para bajar el promedio")
    assert products(app)["PROD-001"]["rating_count"] == 1  # una sola reseña por compra


@pytest.mark.parametrize("rating,comment", [("6", "Comentario suficientemente largo"),
                                            ("0", "Comentario suficientemente largo"),
                                            ("4.5", "Comentario suficientemente largo"), ("5", "corto")])
def test_review_validation(as_bob, app, client, rating, comment):
    _deliver(as_bob, app, client)
    review(client, rating, comment)
    assert products(app)["PROD-001"].get("rating_count", 0) == 0


def test_review_text_is_escaped(as_bob, app, client):
    _deliver(as_bob, app, client)
    review(client, "5", "<script>alert('xss')</script> muy bueno")
    body = client.get("/items/PROD-001").get_data(as_text=True)
    assert "<script>alert('xss')</script>" not in body
    assert "&lt;script&gt;" in body


def test_review_author_name_comes_from_session(as_bob, app, client):
    _deliver(as_bob, app, client)
    post(client, "/items/PROD-001/reviews", {"rating": "5", "comment": "Me gustó mucho el producto",
                                             "author_name": "Administrador Oficial"}, "/items/PROD-001")
    body = client.get("/items/PROD-001").get_data(as_text=True)
    assert "Administrador Oficial" not in body and "Bob P." in body


def test_catalog_shows_rating_and_description(app, client):
    items = products(app)
    items["PROD-001"].update({"rating_sum": Decimal(9), "rating_count": Decimal(2), "rating_5": Decimal(1),
                              "rating_4": Decimal(1), "description": "Pantalla 144 Hz y RTX"})
    body = client.get("/items/").get_data(as_text=True)
    assert "4.5" in body and "Pantalla 144 Hz y RTX" in body
    detail = client.get("/items/PROD-001").get_data(as_text=True)
    assert 'value="50"' in detail  # histograma: 50% de cinco estrellas


# ---------------------------------------------------------------- comandos de consola
def test_check_aws_reports_every_store_route(app):
    result = app.test_cli_runner().invoke(args=["check-aws"])
    assert result.exit_code == 0, result.output
    for label in ("GET /cart: OK", "GET /favorites: OK", "GET /orders: OK", "GET /sales: OK",
                  "GET /products/{id}/reviews: OK"):
        assert label in result.output
    assert app.config["PRODUCTS_API_TOKEN"] not in result.output


def test_seed_demo_publishes_products_with_description(app, monkeypatch):
    for name, value in {"SEED_ADMIN_EMAIL": "ada@marketplace.mx", "SEED_ADMIN_PASSWORD": "Seed-Admin-Test-2026!",
                        "SEED_USER_EMAIL": "luis@marketplace.mx",
                        "SEED_USER_PASSWORD": "Seed-Seller-Test-2026!"}.items():
        monkeypatch.setenv(name, value)
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    seeded = [p for p in products(app).values() if p["name"] == "Laptop HP Victus" and p["seller_id"] != "SEL-000001"]
    assert seeded and seeded[0]["description"].startswith("Laptop para juego")
