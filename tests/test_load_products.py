"""Generador de productos de demostración (tools/load_products.py)."""
from tools import load_products as lp


def test_generates_unique_valid_products():
    items = list(lp.generate(2000, ["SEL-123456", "SEL-654321"]))
    assert len(items) == 2000
    for key in ("product_id", "name", "seller_sku"):
        assert len({item[key] for item in items}) == 2000     # sin repetidos
    for item in items:
        lp.check(item)
        assert item["listed_category"] == item["category"] and item["status"] == "ACTIVE"
        assert item["rating_count"] == sum(item[f"rating_{n}"] for n in range(1, 6))
        assert item["rating_sum"] == sum(n * item[f"rating_{n}"] for n in range(1, 6))


def test_generated_products_are_accepted_by_the_app():
    from Interfaces.ProductServiceInterface.ProductDTO import ProductDTO
    from tests.aws_fakes import FakeDynamo, load_lambdas
    public = load_lambdas(FakeDynamo(), "t" * 48)["lambdaGetProduct"].public
    for item in lp.generate(300, ["SEL-123456"]):
        assert ProductDTO.from_api(public(item)).product_id == item["product_id"]


def test_ids_are_deterministic_so_undo_can_find_them():
    ids = [item["product_id"] for item in lp.generate(3, ["SEL-123456"])]
    assert ids == ["PROD-90000000", "PROD-90000001", "PROD-90000002"]
