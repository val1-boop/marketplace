def test_public_detail_hides_internal_seller_code_and_shows_sku(client):
    page = client.get("/items/PROD-001").get_data(as_text=True)
    assert "SEL-000001" not in page and "Código de vendedor" not in page
    assert "LAP-HP-001" in page   # SKU del producto de prueba