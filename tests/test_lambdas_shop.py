"""Lambdas de compra: carrito, favoritos, pedidos, estados, ventas y reseñas.

Se ejecuta el código REAL de aws/lambdas/ contra las 4 tablas simuladas (tests/aws_fakes.py).
Además de los flujos felices, cada bloque prueba los ataques típicos: precio manipulado,
carrito o pedido ajeno (IDOR), saltos de estado, reseñas sin compra y existencias.
"""
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from .aws_fakes import FakeDynamo, load_lambdas, make_event, seed_item

TOKEN = "t" * 48
ALICE = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000001",
         "x-mkt-actor-user": "00000000-0000-4000-8000-000000000002"}
BOB = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000002",
       "x-mkt-actor-user": "00000000-0000-4000-8000-000000000003"}
CAROL = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000003",
         "x-mkt-actor-user": "00000000-0000-4000-8000-000000000004"}
ADMIN = {"x-mkt-actor-role": "admin", "x-mkt-actor-seller": "",
         "x-mkt-actor-user": "00000000-0000-4000-8000-000000000001"}
ADDRESS = {"recipient_name": "Bob Prueba", "phone": "5512345678", "line1": "Av. Reforma 100",
           "line2": "Depto 4", "city": "Cuauhtémoc", "state": "Ciudad de México", "postal_code": "06600"}


class Ctx:
    aws_request_id = "req-1"


@pytest.fixture
def env():
    dynamo = FakeDynamo()
    products = dynamo.tables["Products"]
    seed_item(products, "PROD-001", "Laptop HP Victus", "SEL-000001", "18500.00", 7)
    seed_item(products, "PROD-002", "Mouse Logitech", "SEL-000001", "500.00", 25, "computer-accessories")
    seed_item(products, "PROD-003", "Monitor 27", "SEL-000003", "6499.50", 2, "monitors")
    return dynamo, load_lambdas(dynamo, TOKEN)


def call(lambdas, name, method, path, actor=None, body=None, pid=None, oid=None):
    headers = dict(actor or {})
    params = {}
    if pid:
        params["product_id"] = pid
    if oid:
        params["order_id"] = oid
    raw = json.dumps(body) if body is not None and not isinstance(body, str) else body
    result = lambdas[name].lambda_handler(make_event(method, path, headers, raw, params or None), Ctx())
    return result["statusCode"], json.loads(result["body"])


def add(lambdas, actor, pid, quantity=1, mode="add"):
    return call(lambdas, "lambdaPutCartItem", "PUT", f"/cart/{pid}", actor,
                {"quantity": quantity, "mode": mode}, pid=pid)


def checkout(lambdas, actor, address=None):
    return call(lambdas, "lambdaCreateOrder", "POST", "/orders", actor, {"address": address or ADDRESS})


def advance(lambdas, actor, oid, action):
    return call(lambdas, "lambdaUpdateOrderStatus", "PUT", f"/orders/{oid}", actor, {"action": action}, oid=oid)


# ------------------------------------------------------------------ generador
def test_lambda_files_are_built_from_source():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run([sys.executable, str(root / "tools" / "build_lambdas.py"), "--check"],
                            capture_output=True, text=True, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ carrito
def test_cart_add_view_and_remove(env):
    dynamo, lambdas = env
    assert add(lambdas, BOB, "PROD-001", 2)[0] == 200
    assert add(lambdas, BOB, "PROD-001", 1)[1]["quantity"] == 3          # "add" suma
    assert add(lambdas, BOB, "PROD-001", 1, "set")[1]["quantity"] == 1   # "set" reemplaza
    status, body = call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)
    assert status == 200 and body["total"] == "18500.00"
    assert body["lineas"][0]["producto"]["name"] == "Laptop HP Victus"
    row = dynamo.tables["Marketplace"].items[("USER#" + BOB["x-mkt-actor-user"], "CART#PROD-001")]
    assert row["expires_at"] > 0                                          # TTL de 30 días
    assert call(lambdas, "lambdaDeleteCartItem", "DELETE", "/cart/PROD-001", BOB, pid="PROD-001")[0] == 200
    assert call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)[1]["lineas"] == []


def test_cart_price_always_comes_from_dynamodb(env):
    dynamo, lambdas = env
    status, body = call(lambdas, "lambdaPutCartItem", "PUT", "/cart/PROD-001", BOB,
                        {"quantity": 1, "price": "1.00"}, pid="PROD-001")
    assert status == 400                                                  # el precio NO se acepta
    add(lambdas, BOB, "PROD-001")
    dynamo.tables["Products"].items["PROD-001"]["price"] = Decimal("19999.00")
    assert call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)[1]["total"] == "19999.00"


@pytest.mark.parametrize("quantity", [0, -1, 11, "abc", 1.5, True, None])
def test_cart_rejects_bad_quantities(env, quantity):
    _, lambdas = env
    assert add(lambdas, BOB, "PROD-001", quantity)[0] == 400


def test_cart_rules(env):
    dynamo, lambdas = env
    assert add(lambdas, ALICE, "PROD-001")[0] == 409                      # su propio producto
    assert add(lambdas, BOB, "PROD-003", 3)[0] == 409                     # solo hay 2
    assert add(lambdas, BOB, "PROD-999")[0] == 404
    dynamo.tables["Products"].items["PROD-002"]["status"] = "BLOCKED"
    assert add(lambdas, BOB, "PROD-002")[0] == 404
    assert add(lambdas, ADMIN, "PROD-001")[0] == 403                      # el admin no compra
    assert add(lambdas, {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000002"}, "PROD-001")[0] == 403


def test_cart_is_private(env):
    dynamo, lambdas = env
    add(lambdas, BOB, "PROD-001")
    assert call(lambdas, "lambdaGetCart", "GET", "/cart", CAROL)[1]["lineas"] == []
    call(lambdas, "lambdaDeleteCartItem", "DELETE", "/cart/PROD-001", CAROL, pid="PROD-001")
    assert len(call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)[1]["lineas"]) == 1


def test_cart_line_limit(env):
    dynamo, lambdas = env
    for n in range(10, 21):
        seed_item(dynamo.tables["Products"], f"PROD-0{n}", f"Producto {n}", "SEL-000003", "10.00", 5)
    for n in range(10, 20):
        assert add(lambdas, BOB, f"PROD-0{n}")[0] == 200
    assert add(lambdas, BOB, "PROD-020")[0] == 409


# ------------------------------------------------------------------ favoritos
def test_favorites_add_list_remove_and_privacy(env):
    dynamo, lambdas = env
    assert call(lambdas, "lambdaAddFavorite", "PUT", "/favorites/PROD-001", BOB, pid="PROD-001")[0] == 200
    assert call(lambdas, "lambdaAddFavorite", "PUT", "/favorites/PROD-001", BOB, pid="PROD-001")[0] == 200
    favs = call(lambdas, "lambdaListFavorites", "GET", "/favorites", BOB)[1]["favoritos"]
    assert [f["product_id"] for f in favs] == ["PROD-001"]
    assert call(lambdas, "lambdaListFavorites", "GET", "/favorites", CAROL)[1]["favoritos"] == []
    assert call(lambdas, "lambdaAddFavorite", "PUT", "/favorites/PROD-404", BOB, pid="PROD-404")[0] == 404
    call(lambdas, "lambdaDeleteFavorite", "DELETE", "/favorites/PROD-001", BOB, pid="PROD-001")
    assert call(lambdas, "lambdaListFavorites", "GET", "/favorites", BOB)[1]["favoritos"] == []


# ------------------------------------------------------------------ compra
def test_checkout_creates_one_order_per_seller_and_empties_cart(env):
    dynamo, lambdas = env
    add(lambdas, BOB, "PROD-001", 1)
    add(lambdas, BOB, "PROD-002", 2)
    add(lambdas, BOB, "PROD-003", 1)
    status, body = checkout(lambdas, BOB)
    assert status == 201
    orders = body["pedidos"]
    assert len(orders) == 2                                               # SEL-000001 y SEL-000003
    totals = sorted(o["total"] for o in orders)
    assert totals == ["19500.00", "6499.50"]
    products = dynamo.tables["Products"].items
    assert products["PROD-001"]["stock"] == 6 and products["PROD-002"]["stock"] == 23
    assert products["PROD-003"]["stock"] == 1 and products["PROD-002"]["sales_count"] == 2
    assert call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)[1]["lineas"] == []
    assert dynamo.transactions == 1                                       # todo en una transacción
    mine = call(lambdas, "lambdaListOrders", "GET", "/orders", BOB)[1]["pedidos"]
    assert {o["order_id"] for o in mine} == {o["order_id"] for o in orders}
    assert all(o["status"] == "CONFIRMED" and o["estimated_from"] < o["estimated_to"] for o in mine)


def test_checkout_rejects_empty_cart_bad_address_and_extra_fields(env):
    _, lambdas = env
    assert checkout(lambdas, BOB)[0] == 400                               # carrito vacío
    add(lambdas, BOB, "PROD-001")
    for bad in [dict(ADDRESS, postal_code="123"), dict(ADDRESS, phone="55-1234"),
                dict(ADDRESS, state="Texas"), dict(ADDRESS, line1="<"), dict(ADDRESS, admin=True)]:
        assert checkout(lambdas, BOB, bad)[0] == 400
    status, _ = call(lambdas, "lambdaCreateOrder", "POST", "/orders", BOB,
                     {"address": ADDRESS, "total": "1.00"})
    assert status == 400                                                  # el total no viene del cliente


def test_checkout_is_all_or_nothing_when_stock_runs_out(env):
    dynamo, lambdas = env
    add(lambdas, BOB, "PROD-001", 1)
    add(lambdas, BOB, "PROD-003", 2)
    dynamo.tables["Products"].items["PROD-003"]["stock"] = Decimal(1)    # alguien compró antes
    status, _ = checkout(lambdas, BOB)
    assert status == 409
    assert dynamo.tables["Products"].items["PROD-001"]["stock"] == 7      # nada a medias
    assert dynamo.tables["Orders"].items == {}
    assert len(call(lambdas, "lambdaGetCart", "GET", "/cart", BOB)[1]["lineas"]) == 2


def test_transaction_race_is_reported_as_conflict(env, monkeypatch):
    dynamo, lambdas = env
    add(lambdas, BOB, "PROD-003", 2)
    real = dynamo.transact_write_items

    def steal_last_unit(TransactItems):
        dynamo.tables["Products"].items["PROD-003"]["stock"] = Decimal(1)
        return real(TransactItems)

    dynamo.meta.client.transact_write_items = steal_last_unit
    assert checkout(lambdas, BOB)[0] == 409
    assert dynamo.tables["Orders"].items == {}


# ------------------------------------------------------------------ estados y ventas
def _one_order(env, buyer=BOB, pid="PROD-001", qty=1):
    _, lambdas = env
    add(lambdas, buyer, pid, qty)
    return checkout(lambdas, buyer)[1]["pedidos"][0]["order_id"]


def test_full_lifecycle_and_who_can_do_what(env):
    dynamo, lambdas = env
    oid = _one_order(env)
    assert advance(lambdas, BOB, oid, "prepare")[0] == 403                # el comprador no prepara
    assert advance(lambdas, ALICE, oid, "ship")[0] == 409                 # no se saltan estados
    assert advance(lambdas, ALICE, oid, "prepare")[0] == 200
    assert advance(lambdas, ALICE, oid, "ship")[0] == 200
    assert advance(lambdas, ALICE, oid, "deliver")[0] == 403              # entregar lo confirma el comprador
    status, body = advance(lambdas, BOB, oid, "deliver")
    assert status == 200 and body["pedido"]["status"] == "DELIVERED"
    assert [h["status"] for h in body["pedido"]["history"]] == ["CONFIRMED", "PREPARING", "SHIPPED", "DELIVERED"]
    assert body["pedido"]["shipment"]["shipped_at"] and body["pedido"]["shipment"]["delivered_at"]
    assert advance(lambdas, BOB, oid, "cancel")[0] == 409                 # ya entregado: no se cancela
    header = dynamo.tables["Orders"].items[(f"ORDER#{oid}", "ORDER")]
    assert header["GSI2PK"] == "STATUS#DELIVERED"


def test_order_detail_is_private_and_seller_sees_sales(env):
    _, lambdas = env
    oid = _one_order(env)
    assert call(lambdas, "lambdaGetOrder", "GET", f"/orders/{oid}", BOB, oid=oid)[0] == 200
    status, body = call(lambdas, "lambdaGetOrder", "GET", f"/orders/{oid}", ALICE, oid=oid)
    assert status == 200 and body["pedido"]["viewer"] == "seller"
    assert body["pedido"]["shipment"]["postal_code"] == "06600"           # el vendedor ve a dónde enviar
    assert call(lambdas, "lambdaGetOrder", "GET", f"/orders/{oid}", CAROL, oid=oid)[0] == 404
    assert call(lambdas, "lambdaGetOrder", "GET", "/orders/X", BOB, oid="../../x")[0] == 404
    assert advance(lambdas, CAROL, oid, "cancel")[0] == 404
    sales = call(lambdas, "lambdaListSales", "GET", "/sales", ALICE)[1]["ventas"]
    assert [s["order_id"] for s in sales] == [oid]
    assert call(lambdas, "lambdaListSales", "GET", "/sales", CAROL)[1]["ventas"] == []
    assert call(lambdas, "lambdaListOrders", "GET", "/orders", CAROL)[1]["pedidos"] == []


def test_cancel_returns_stock(env):
    dynamo, lambdas = env
    oid = _one_order(env, qty=3)
    assert dynamo.tables["Products"].items["PROD-001"]["stock"] == 4
    assert advance(lambdas, BOB, oid, "cancel")[0] == 200
    assert dynamo.tables["Products"].items["PROD-001"]["stock"] == 7
    assert advance(lambdas, BOB, oid, "cancel")[0] == 409                 # no se cancela dos veces


def test_seller_can_cancel_while_preparing_but_buyer_cannot(env):
    _, lambdas = env
    oid = _one_order(env)
    advance(lambdas, ALICE, oid, "prepare")
    assert advance(lambdas, BOB, oid, "cancel")[0] == 409
    assert advance(lambdas, ALICE, oid, "cancel")[0] == 200


@pytest.mark.parametrize("body", [{"action": "teleport"}, {"action": "prepare", "status": "DELIVERED"},
                                  {"action": "cancel", "reason": "x"}])
def test_status_update_rejects_bad_bodies(env, body):
    _, lambdas = env
    oid = _one_order(env)
    status, _ = call(lambdas, "lambdaUpdateOrderStatus", "PUT", f"/orders/{oid}", ALICE, body, oid=oid)
    assert status == 400


# ------------------------------------------------------------------ reseñas
def _delivered(env, buyer=BOB, pid="PROD-001"):
    _, lambdas = env
    oid = _one_order(env, buyer=buyer, pid=pid)
    advance(lambdas, ALICE, oid, "prepare")
    advance(lambdas, ALICE, oid, "ship")
    advance(lambdas, buyer, oid, "deliver")
    return oid


def review(lambdas, actor, pid="PROD-001", rating=5, comment="Excelente, llegó a tiempo.", author="Bob P."):
    return call(lambdas, "lambdaCreateReview", "POST", f"/products/{pid}/reviews", actor,
                {"rating": rating, "comment": comment, "author_name": author}, pid=pid)


def test_only_buyers_with_delivered_orders_can_review_once(env):
    dynamo, lambdas = env
    assert review(lambdas, BOB)[0] == 403                                 # no lo ha comprado
    oid = _one_order(env)
    assert review(lambdas, BOB)[0] == 403                                 # comprado pero no entregado
    advance(lambdas, ALICE, oid, "prepare")
    advance(lambdas, ALICE, oid, "ship")
    advance(lambdas, BOB, oid, "deliver")
    listing = call(lambdas, "lambdaListReviews", "GET", "/products/PROD-001/reviews", BOB, pid="PROD-001")[1]
    assert listing["puede_opinar"] is True
    assert review(lambdas, BOB, rating=4)[0] == 201
    assert review(lambdas, BOB, rating=1)[0] == 403                       # solo una vez
    product = dynamo.tables["Products"].items["PROD-001"]
    assert product["rating_sum"] == 4 and product["rating_count"] == 1 and product["rating_4"] == 1
    listing = call(lambdas, "lambdaListReviews", "GET", "/products/PROD-001/reviews", BOB, pid="PROD-001")[1]
    assert listing["puede_opinar"] is False
    assert listing["resenas"][0]["rating"] == 4 and listing["resenas"][0]["author_name"] == "Bob P."
    public = call(lambdas, "lambdaGetProduct", "GET", "/products/PROD-001", None, pid="PROD-001")[1]["producto"]
    assert public["rating_avg"] == "4.0" and public["rating_count"] == 1
    assert public["rating_dist"]["4"] == 1


def test_average_rating_from_several_buyers(env):
    dynamo, lambdas = env
    _delivered(env, BOB)
    _delivered(env, CAROL)
    review(lambdas, BOB, rating=5)
    review(lambdas, CAROL, rating=4, author="Carol P.")
    public = call(lambdas, "lambdaGetProduct", "GET", "/products/PROD-001", None, pid="PROD-001")[1]["producto"]
    assert public["rating_avg"] == "4.5" and public["rating_count"] == 2


@pytest.mark.parametrize("override", [
    {"rating": 0}, {"rating": 6}, {"rating": "5"}, {"rating": 4.5},
    {"comment": "corto"}, {"comment": "x" * 1001}, {"comment": "malo\x00malo malo"},
    {"author": "<script>"}, {"author": "Admin123"},
])
def test_review_validation(env, override):
    _, lambdas = env
    _delivered(env)
    args = {"rating": 5, "comment": "Muy buen producto, lo recomiendo.", "author": "Bob P."}
    args.update(override)
    assert review(lambdas, BOB, **args)[0] == 400


def test_reviews_are_public_and_safe(env):
    _, lambdas = env
    _delivered(env)
    review(lambdas, BOB, comment="<script>alert(1)</script> muy bueno")
    status, body = call(lambdas, "lambdaListReviews", "GET", "/products/PROD-001/reviews", None, pid="PROD-001")
    assert status == 200 and body["puede_opinar"] is False
    assert "buyer_id" not in json.dumps(body) and "USER#" not in json.dumps(body)
    # El texto se guarda tal cual; Flask lo muestra escapado (ver test de la ficha).
    assert body["resenas"][0]["comment"].startswith("<script>")


def test_review_extra_fields_rejected(env):
    _, lambdas = env
    _delivered(env)
    status, _ = call(lambdas, "lambdaCreateReview", "POST", "/products/PROD-001/reviews", BOB,
                     {"rating": 5, "comment": "Muy buen producto.", "author_name": "Bob P.", "verified": True},
                     pid="PROD-001")
    assert status == 400


# ------------------------------------------------------------------ productos con descripción
def test_product_description_round_trip(env):
    _, lambdas = env
    body = {"name": "Teclado compacto", "description": "Teclado 60%.\nSwitches rojos.",
            "category": "computer-accessories", "price": "799.00", "stock": 3, "condition": "NEW"}
    status, data = call(lambdas, "lambdaCreateProduct", "POST", "/products", BOB, body)
    assert status == 201 and data["producto"]["description"] == "Teclado 60%.\nSwitches rojos."
    assert data["producto"]["rating_avg"] == "0.0"
    status, data = call(lambdas, "lambdaCreateProduct", "POST", "/products", BOB,
                        dict(body, description="x" * 2001))
    assert status == 400
