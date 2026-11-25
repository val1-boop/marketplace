"""Sin sesión, una acción (POST) manda al login y, al entrar, se regresa a la página de origen.

Como en un marketplace: se puede mirar todo sin cuenta; al pulsar "Agregar al carrito" se pide iniciar
sesión y después se vuelve a la ficha del producto (no a la dirección de la acción, que solo admite POST).
"""
import pytest

from View.SharedViews.PY.SafeNext import origin_page

from .conftest import BASE_URL, get_csrf, login

FICHA = "/items/PROD-001"


def _post_anonymous(client, path, referer):
    token = get_csrf(client, "/auth/login")
    return client.post(path, data={"csrf_token": token, "quantity": "1"}, headers={"Referer": referer})


def test_anonymous_post_returns_to_the_product_page_after_login(client):
    response = _post_anonymous(client, "/cart/add/PROD-001", BASE_URL + FICHA)
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login?next=%2Fitems%2FPROD-001"
    after = login(client, "bob", next_url=FICHA)
    assert after.status_code == 302 and after.headers["Location"] == FICHA
    assert client.get(after.headers["Location"]).status_code == 200      # ya no es un 405


@pytest.mark.parametrize("path", ["/cart/add/PROD-001", "/cart/buy/PROD-001", "/favorites/add/PROD-001",
                                  "/items/PROD-001/reviews", "/checkout", "/items/new"])
def test_every_protected_action_returns_to_the_origin_page(client, path):
    response = _post_anonymous(client, path, BASE_URL + FICHA + "?x=1")
    assert response.headers["Location"] == "/auth/login?next=%2Fitems%2FPROD-001%3Fx%3D1"


def test_origin_in_the_catalog_returns_to_the_catalog(client):
    response = _post_anonymous(client, "/favorites/add/PROD-001", BASE_URL + "/items/?q=laptop&page=2")
    assert response.headers["Location"] == "/auth/login?next=%2Fitems%2F%3Fq%3Dlaptop%26page%3D2"


@pytest.mark.parametrize("referer", [
    "https://evil.com/items/PROD-001",            # otro sitio
    "https://localhost.evil.com/items/PROD-001",  # dominio que solo empieza igual
    "https://localhost@evil.com/items/PROD-001",  # credenciales falsas en la URL
    "http://localhost/items/PROD-001",            # esquema distinto
])
def test_foreign_referer_is_rejected_before_any_redirect(client, referer):
    """En HTTPS, Flask-WTF ya exige un Referer del propio sitio: no se llega a redirigir a ningún lado."""
    response = _post_anonymous(client, "/cart/add/PROD-001", referer)
    assert response.status_code == 400 and "Location" not in response.headers


@pytest.mark.parametrize("referer,expected", [
    ("https://localhost/items/PROD-001?a=1", "/items/PROD-001?a=1"),
    ("https://localhost/", "/"),
    ("https://localhost/auth/login", None),            # no volver a una pantalla de acceso (bucle)
    ("https://localhost/auth/register", None),
    ("https://evil.com/items/PROD-001", None),
    ("https://localhost.evil.com/items/PROD-001", None),
    ("https://localhost@evil.com/items/PROD-001", None),
    ("https://localhost:8443/items/PROD-001", None),   # otro puerto = otro origen
    ("//evil.com/x", None),
    ("javascript:alert(1)", None),
    ("not a url", None),
    ("https://localhost//evil.com", None),             # ruta con doble barra inicial
    ("https://[::1", None),                            # URL mal formada
    ("", None),
])
def test_origin_page_validates_the_referer(app, referer, expected):
    with app.test_request_context("/cart/add/PROD-001", base_url=BASE_URL, headers={"Referer": referer}):
        assert origin_page() == expected


def test_origin_page_without_referer_is_none(app):
    with app.test_request_context("/cart/add/PROD-001", base_url=BASE_URL):
        assert origin_page() is None


def test_get_to_a_protected_page_still_remembers_it(client):
    response = client.get("/cart/")
    assert response.status_code == 302 and response.headers["Location"] == "/auth/login?next=%2Fcart%2F"
    response = client.get("/orders/?page=2")
    assert response.headers["Location"] == "/auth/login?next=%2Forders%2F%3Fpage%3D2"


def test_the_login_message_is_still_shown(client):
    _post_anonymous(client, "/cart/add/PROD-001", BASE_URL + FICHA)
    page = client.get("/auth/login").get_data(as_text=True)
    assert "Inicia sesión para continuar." in page


def test_wrong_role_is_still_forbidden_not_redirected(as_admin):
    assert as_admin.get("/items/new").status_code == 403
