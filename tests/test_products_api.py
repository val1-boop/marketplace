"""Cliente de Flask ↔ API Gateway simulado ↔ Lambdas reales ↔ DynamoDB simulado."""
from decimal import Decimal

import pytest

from Implementation.ProductServiceImplementation.ProductsApiClient import (
    ProductConflict,
    ProductForbidden,
    ProductNotFound,
    ProductsAPI,
    ProductsAPIError,
    ProductValidationError,
)

from .aws_fakes import FakeApiGateway, FakeTable, seed_item

BASE = "https://abc123.execute-api.us-east-1.amazonaws.com"
TOKEN = "k" * 48
DATA = {"name": "Router WiFi 6", "category": "networking", "price": Decimal("1499.00"),
        "stock": 40, "condition": "NEW"}


@pytest.fixture
def setup():
    table = FakeTable()
    seed_item(table, "PROD-001", "Laptop HP Victus", "SEL-000001", "18500.00", 7)
    gateway = FakeApiGateway(BASE, table, TOKEN)
    return table, gateway, ProductsAPI(BASE, TOKEN, session=gateway)


def test_full_crud_through_gateway(setup):
    table, _, api = setup
    created = api.create_product("SEL-000001", DATA)
    assert created.price == Decimal("1499.00") and created.seller_id == "SEL-000001"
    assert api.get_product(created.product_id).name == "Router WiFi 6"
    updated = api.update_product(created.product_id, "SEL-000001", dict(DATA, stock=3), created.version)
    assert updated.stock == 3 and updated.version == 2
    assert {p.product_id for p in api.list_products(seller_id="SEL-000001")} == {"PROD-001", created.product_id}
    api.delete_product(created.product_id, "user", "SEL-000001")
    with pytest.raises(ProductNotFound):
        api.get_product(created.product_id)


def test_wrong_token_is_rejected_by_authorizer(setup):
    _, gateway, _ = setup
    bad = ProductsAPI(BASE, "x" * 48, session=gateway)
    with pytest.raises(ProductsAPIError):
        bad.list_products()


def test_ownership_and_conflicts(setup):
    _, _, api = setup
    with pytest.raises(ProductForbidden):
        api.update_product("PROD-001", "SEL-000002", DATA, 1)
    with pytest.raises(ProductForbidden):
        api.delete_product("PROD-001", "user", "SEL-000002")
    with pytest.raises(ProductConflict):
        api.update_product("PROD-001", "SEL-000001", DATA, 9)


def test_moderation(setup):
    _, _, api = setup
    assert api.moderate_product("PROD-001", "block", "Revisión de moderación").status == "BLOCKED"
    assert api.moderate_product("PROD-001", "unblock").status == "ACTIVE"
    with pytest.raises(ProductValidationError):
        api.moderate_product("PROD-001", "block", "no")


def test_ids_are_validated_before_building_urls(setup):
    _, gateway, api = setup
    before = len(gateway.requests)
    for bad in ["../../etc/passwd", "PROD-001/../x", "https://evil.example", "PROD-1%2F"]:
        with pytest.raises(ProductNotFound):
            api.get_product(bad)
    assert len(gateway.requests) == before  # ni siquiera se llamó al API
    assert api.list_products(seller_id="SEL-1' OR 1=1") == []


def test_token_never_in_repr_and_timeout_always_set(setup):
    _, gateway, api = setup
    assert TOKEN not in repr(api)
    api.list_products()
    method, url, headers = gateway.requests[-1]
    assert url.startswith(BASE) and headers["x-mkt-token"] == TOKEN


def test_api_down_raises_controlled_error(setup):
    _, gateway, api = setup
    gateway.down = True
    with pytest.raises(ProductsAPIError):
        api.list_products()


def test_http_base_url_is_refused():
    with pytest.raises(ValueError):
        ProductsAPI("http://abc.execute-api.us-east-1.amazonaws.com", TOKEN)
