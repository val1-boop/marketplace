def test_public_detail_hides_internal_seller_code_and_shows_sku(client):
    page = client.get("/items/PROD-001").get_data(as_text=True)
    assert "SEL-000001" not in page and "Código de vendedor" not in page
    assert "LAP-HP-001" in page   # SKU del producto de prueba
    
    

def test_owner_detail_links_to_my_products_instead_of_edit_buttons(as_alice):
    page = as_alice.get("/items/PROD-001").get_data(as_text=True)
    assert "Administrar en Mis productos" in page and "Editar producto" not in page and "Eliminar" not in page
    
    

def test_my_products_searches_by_sku_and_hides_the_seller_code(as_alice):
    page = as_alice.get("/items/mine").get_data(as_text=True)
    assert "Buscar por nombre o SKU" in page and "Código de vendedor" not in page