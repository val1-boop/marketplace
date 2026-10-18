"""Pruebas del código REAL de las Lambdas (aws/lambdas/) contra una tabla simulada."""
import json

import pytest

from .aws_fakes import FakeTable, load_lambdas, make_event, seed_item

TOKEN = "t" * 48
USER_A = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000001"}
USER_B = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-000002"}
ADMIN = {"x-mkt-actor-role": "admin", "x-mkt-actor-seller": ""}
VALID = {"name": "Teclado compacto", "category": "computer-accessories",
         "price": "749.00", "stock": 15, "condition": "NEW"}


class Ctx:
    aws_request_id = "req-1"


@pytest.fixture
def env():
    table = FakeTable()
    seed_item(table, "PROD-001", "Laptop HP Victus", "SEL-000001", "18500.00", 7)
    seed_item(table, "PROD-002", "Mouse Logitech", "SEL-000002", "500.00", 25, "computer-accessories")
    return table, load_lambdas(table, TOKEN)


def call(lambdas, name, method, path, headers=None, body=None, pid=None, query=None):
    raw = json.dumps(body) if isinstance(body, dict) else body
    event = make_event(method, path, headers, raw, {"product_id": pid} if pid else None, query)
    result = lambdas[name].lambda_handler(event, Ctx())
    return result["statusCode"], json.loads(result["body"])


# ------------------------------------------------------------------ autorizador
def test_authorizer_accepts_only_exact_token(env):
    _, lambdas = env
    handler = lambdas["lambdaAuthorizer"].lambda_handler
    assert handler(make_event("GET", "/products", {"x-mkt-token": TOKEN}), Ctx()) == {"isAuthorized": True}
    for bad in ["", "t" * 47, TOKEN + "x", TOKEN.upper(), "' OR '1'='1"]:
        assert handler(make_event("GET", "/products", {"x-mkt-token": bad}), Ctx())["isAuthorized"] is False
    assert handler(make_event("GET", "/products", {}), Ctx())["isAuthorized"] is False


def test_authorizer_fails_closed_with_weak_or_missing_secret():
    table = FakeTable()
    lambdas = load_lambdas(table, "corto")
    event = make_event("GET", "/products", {"x-mkt-token": "corto"})
    assert lambdas["lambdaAuthorizer"].lambda_handler(event, Ctx())["isAuthorized"] is False


# ------------------------------------------------------------------ listar / obtener
def test_list_all_and_by_seller(env):
    table, lambdas = env
    status, body = call(lambdas, "lambdaListProducts", "GET", "/products")
    assert status == 200 and len(body["productos"]) == 2
    status, body = call(lambdas, "lambdaListProducts", "GET", "/products", query={"seller_id": "SEL-000001"})
    assert [p["product_id"] for p in body["productos"]] == ["PROD-001"]
    assert "query:bySeller" in table.calls


def test_list_rejects_bad_seller_filter(env):
    _, lambdas = env
    status, _ = call(lambdas, "lambdaListProducts", "GET", "/products", query={"seller_id": "' OR 1=1"})
    assert status == 400


def test_get_product_and_output_whitelist(env):
    table, lambdas = env
    table.items["PROD-001"]["secreto_interno"] = "no-debe-salir"
    status, body = call(lambdas, "lambdaGetProduct", "GET", "/products/PROD-001", pid="PROD-001")
    assert status == 200
    assert body["producto"]["price"] == "18500.00"
    assert "secreto_interno" not in body["producto"]


@pytest.mark.parametrize("pid", ["PROD-999", "../etc/passwd", "PROD-001' OR '1'='1", "", "prod-001"])
def test_get_unknown_or_malformed_id_is_404(env, pid):
    _, lambdas = env
    status, _ = call(lambdas, "lambdaGetProduct", "GET", f"/products/{pid}", pid=pid or None)
    assert status == 404


# ------------------------------------------------------------------ crear
def test_create_assigns_server_side_id_and_seller(env):
    table, lambdas = env
    body = dict(VALID, seller_id="SEL-000002")  # intento de suplantar vendedor
    status, data = call(lambdas, "lambdaCreateProduct", "POST", "/products", USER_A, body)
    assert status == 400  # seller_id es un campo no permitido en el cuerpo
    status, data = call(lambdas, "lambdaCreateProduct", "POST", "/products", USER_A, VALID)
    assert status == 201
    product = data["producto"]
    assert product["seller_id"] == "SEL-000001"
    assert product["product_id"].startswith("PROD-") and len(product["product_id"]) == 13
    stored = table.items[product["product_id"]]
    assert stored["listed_category"] == "computer-accessories" and stored["status"] == "ACTIVE"


@pytest.mark.parametrize("override", [
    {"name": "ab"}, {"name": "x" * 121}, {"name": "malo\x00"}, {"name": 123},
    {"price": "0"}, {"price": "-5"}, {"price": "NaN"}, {"price": "Infinity"}, {"price": "1e309"},
    {"price": "10.999"}, {"price": True}, {"stock": -1}, {"stock": 1.5}, {"stock": "abc"},
    {"stock": 100001}, {"category": "../../x"}, {"condition": "ROBADO"},
    {"status": "BLOCKED"}, {"product_id": "PROD-001"}, {"version": 99},
])
def test_create_rejects_invalid_or_extra_fields(env, override):
    table, lambdas = env
    status, data = call(lambdas, "lambdaCreateProduct", "POST", "/products", USER_A, dict(VALID, **override))
    assert status == 400, data
    assert len(table.items) == 2


def test_create_requires_seller_actor(env):
    _, lambdas = env
    assert call(lambdas, "lambdaCreateProduct", "POST", "/products", ADMIN, VALID)[0] == 403
    assert call(lambdas, "lambdaCreateProduct", "POST", "/products", {}, VALID)[0] == 403
    bad = {"x-mkt-actor-role": "user", "x-mkt-actor-seller": "SEL-1 OR 1=1"}
    assert call(lambdas, "lambdaCreateProduct", "POST", "/products", bad, VALID)[0] == 403


@pytest.mark.parametrize("raw", [None, "", "no-es-json", "[1,2]", "x" * 9000])
def test_create_rejects_bad_bodies(env, raw):
    _, lambdas = env
    status, _ = call(lambdas, "lambdaCreateProduct", "POST", "/products", USER_A, raw)
    assert status in (400, 413)


# ------------------------------------------------------------------ modificar
def _update(lambdas, headers, pid="PROD-001", version=1, **fields):
    body = {"action": "update", "expected_version": version, "name": "Laptop HP Victus 16",
            "category": "computers", "price": "17999.50", "stock": 4, "condition": "REFURBISHED"}
    body.update(fields)
    return call(lambdas, "lambdaUpdateProduct", "PUT", f"/products/{pid}", headers, body, pid=pid)


def test_owner_updates_product_and_version_increments(env):
    table, lambdas = env
    status, data = _update(lambdas, USER_A)
    assert status == 200
    assert data["producto"]["version"] == 2
    assert data["producto"]["price"] == "17999.50"
    assert table.items["PROD-001"]["search_name"] == "laptop hp victus 16"


def test_idor_update_by_other_seller_is_403(env):
    table, lambdas = env
    status, _ = _update(lambdas, USER_B)
    assert status == 403
    assert table.items["PROD-001"]["name"] == "Laptop HP Victus"


def test_stale_version_is_409(env):
    table, lambdas = env
    assert _update(lambdas, USER_A, version=5)[0] == 409
    assert table.items["PROD-001"]["name"] == "Laptop HP Victus"


def test_update_cannot_change_owner_or_status(env):
    table, lambdas = env
    status, _ = _update(lambdas, USER_A, seller_id="SEL-000002", status="ACTIVE")
    assert status == 400
    assert table.items["PROD-001"]["seller_id"] == "SEL-000001"


def test_admin_cannot_edit_content(env):
    _, lambdas = env
    assert _update(lambdas, ADMIN)[0] == 403


def test_block_unblock_delist_by_admin(env):
    table, lambdas = env
    url = "/products/PROD-002"
    status, data = call(lambdas, "lambdaUpdateProduct", "PUT", url, ADMIN,
                        {"action": "block", "reason": "Producto engañoso"}, pid="PROD-002")
    assert status == 200 and data["producto"]["status"] == "BLOCKED"
    assert "listed_category" not in table.items["PROD-002"]
    status, _ = call(lambdas, "lambdaUpdateProduct", "PUT", url, ADMIN, {"action": "block", "reason": "Otra vez"},
                     pid="PROD-002")
    assert status == 409
    status, data = call(lambdas, "lambdaUpdateProduct", "PUT", url, ADMIN, {"action": "unblock"}, pid="PROD-002")
    assert status == 200 and data["producto"]["status"] == "ACTIVE"
    assert table.items["PROD-002"]["listed_category"] == "computer-accessories"
    assert "blocked_reason" not in table.items["PROD-002"]
    status, data = call(lambdas, "lambdaUpdateProduct", "PUT", url, ADMIN, {"action": "delist"}, pid="PROD-002")
    assert status == 200 and data["producto"]["status"] == "DELISTED"


def test_users_cannot_moderate(env):
    table, lambdas = env
    status, _ = call(lambdas, "lambdaUpdateProduct", "PUT", "/products/PROD-001", USER_A,
                     {"action": "block", "reason": "Me bloqueo yo"}, pid="PROD-001")
    assert status == 403
    assert table.items["PROD-001"]["status"] == "ACTIVE"


def test_block_requires_valid_reason(env):
    _, lambdas = env
    for reason in ["", "abc", "x" * 501, "linea\r\nnueva", 5]:
        status, _ = call(lambdas, "lambdaUpdateProduct", "PUT", "/products/PROD-001", ADMIN,
                         {"action": "block", "reason": reason}, pid="PROD-001")
        assert status == 400


def test_update_unknown_product_is_404(env):
    _, lambdas = env
    assert _update(lambdas, USER_A, pid="PROD-777")[0] == 404


# ------------------------------------------------------------------ eliminar
def test_owner_deletes_own_product(env):
    table, lambdas = env
    status, _ = call(lambdas, "lambdaDeleteProduct", "DELETE", "/products/PROD-001", USER_A, pid="PROD-001")
    assert status == 200 and "PROD-001" not in table.items


def test_idor_delete_by_other_seller_is_403(env):
    table, lambdas = env
    status, _ = call(lambdas, "lambdaDeleteProduct", "DELETE", "/products/PROD-001", USER_B, pid="PROD-001")
    assert status == 403 and "PROD-001" in table.items


def test_admin_deletes_any_product_and_404_after(env):
    table, lambdas = env
    assert call(lambdas, "lambdaDeleteProduct", "DELETE", "/products/PROD-002", ADMIN, pid="PROD-002")[0] == 200
    assert call(lambdas, "lambdaDeleteProduct", "DELETE", "/products/PROD-002", ADMIN, pid="PROD-002")[0] == 404


def test_internal_errors_hide_details(env, capsys):
    table, lambdas = env

    def broken(**_kwargs):
        raise RuntimeError("detalle interno secreto")

    table.scan = broken
    status, body = call(lambdas, "lambdaListProducts", "GET", "/products")
    assert status == 500
    assert "secreto" not in json.dumps(body)
    assert body["request_id"] == "req-1"
    assert "detalle interno secreto" in capsys.readouterr().out  # queda en CloudWatch


def test_responses_have_no_cors_wildcard(env):
    _, lambdas = env
    event = make_event("GET", "/products")
    result = lambdas["lambdaListProducts"].lambda_handler(event, Ctx())
    assert "Access-Control-Allow-Origin" not in result["headers"]
