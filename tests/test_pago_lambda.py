"""Pago simulado registrado por la Lambda de pedidos."""
from .test_lambdas_shop import BOB, add, call, checkout, env  # noqa: F401  (env es un fixture de pytest)


def test_checkout_records_a_simulated_payment(env):  # noqa: F811
    dynamo, lambdas = env
    add(lambdas, BOB, "PROD-001", 2)
    status, body = checkout(lambdas, BOB)
    assert status == 201
    order_id = body["pedidos"][0]["order_id"]
    status, detail = call(lambdas, "lambdaGetOrder", "GET", f"/orders/{order_id}", BOB, oid=order_id)
    assert status == 200
    payment = detail["pedido"]["payment"]
    assert payment["status"] == "PAID" and payment["method"] == "SIMULATED" and payment["amount"] == "37000.00"
    assert payment["paid_at"].endswith("Z")
    # Pago simulado: no se guarda ningún dato de tarjeta, solo estos campos.
    row = dynamo.tables["Orders"].items[(f"ORDER#{order_id}", "PAYMENT")]
    assert set(row) == {"PK", "SK", "entity", "order_id", "status", "method", "amount", "currency", "paid_at"}
