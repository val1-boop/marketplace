"""Fixtures de pytest.

- Cada prueba usa una app nueva con SQLite en memoria y su propio rate limiter.
- El cliente envía todo por HTTPS (las cookies son Secure) y con Referer del mismo
  origen (Flask-WTF valida el Referer en HTTPS con WTF_CSRF_SSL_STRICT).
- El contexto de aplicación NO queda abierto durante las peticiones, para que cada
  petición tenga su propio `g` y su propia sesión de BD, como en producción.
- Los productos pasan por un API Gateway simulado que ejecuta las Lambdas REALES de
  aws/lambdas/ contra una tabla DynamoDB simulada (fixture `table`).
"""
import re

import pytest
from flask.testing import FlaskClient

from Core import create_app
from Core.Extensions import db, limiter
from Models import User, utcnow
from Security import hash_password, normalize_email
from Implementation.ProductServiceImplementation.ProductsApiClient import ProductsAPI

from .aws_fakes import FakeApiGateway, FakeTable, seed_item

BASE_URL = "https://localhost"
PASSWORDS = {
    "admin": "Admin-Clave-Segura-2026!",
    "alice": "Alice-Clave-Segura-2026!",
    "bob": "Bob-Clave-Segura-2026!x",
}
EMAILS = {
    "admin": "admin@marketplace.mx",
    "alice": "alice@marketplace.mx",
    "bob": "bob@marketplace.mx",
}
IDS = {
    "admin": "00000000-0000-4000-8000-000000000001",
    "alice": "00000000-0000-4000-8000-000000000002",
    "bob": "00000000-0000-4000-8000-000000000003",
}
SELLERS = {"alice": "SEL-000001", "bob": "SEL-000002"}
CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


class SecureClient(FlaskClient):
    def open(self, *args, **kwargs):
        if not args or isinstance(args[0], str):
            kwargs.setdefault("base_url", BASE_URL)
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("Referer", BASE_URL + "/")
            kwargs["headers"] = headers
        return super().open(*args, **kwargs)


def _user(key, role):
    now = utcnow()
    return User(
        id=IDS[key], email=EMAILS[key], email_normalized=normalize_email(EMAILS[key]),
        first_name=key.capitalize(), last_name="Prueba",
        password_hash=hash_password(PASSWORDS[key]), role=role, status="active",
        seller_id=SELLERS.get(key), terms_version="2026-10", privacy_version="2026-10",
        terms_accepted_at=now,
    )


@pytest.fixture
def table():
    fake = FakeTable()
    seed_item(fake, "PROD-001", "Laptop HP Victus", SELLERS["alice"], "18500.00", 7, seller_sku="LAP-HP-001")
    seed_item(fake, "PROD-002", "Mouse Logitech", SELLERS["bob"], "500.00", 25, "computer-accessories",
              seller_sku="MOU-LOG-002")
    return fake


@pytest.fixture
def app(table):
    application = create_app("testing")
    application.test_client_class = SecureClient
    url, token = application.config["PRODUCTS_API_URL"], application.config["PRODUCTS_API_TOKEN"]
    gateway = FakeApiGateway(url, table, token)
    application.extensions["products_api"] = ProductsAPI(url, token, session=gateway)
    application.extensions["fake_gateway"] = gateway
    with application.app_context():
        db.create_all()
        db.session.add_all([_user("admin", "admin"), _user("alice", "user"), _user("bob", "user")])
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
    limiter.reset()


@pytest.fixture
def client(app):
    return app.test_client()


def get_csrf(client, path):
    response = client.get(path)
    match = CSRF_RE.search(response.get_data(as_text=True))
    assert match, f"No se encontró token CSRF en {path} (status {response.status_code})"
    return match.group(1)


def login(client, who=None, email=None, password=None, next_url=None):
    token = get_csrf(client, "/auth/login")
    path = "/auth/login" + (f"?next={next_url}" if next_url else "")
    return client.post(path, data={
        "email": email if email is not None else EMAILS[who],
        "password": password if password is not None else PASSWORDS[who],
        "csrf_token": token,
    })


def post_form(client, path, data, token_path=None):
    """Hace GET para obtener el token CSRF de la página y luego POST."""
    token = get_csrf(client, token_path or path)
    payload = dict(data)
    payload["csrf_token"] = token
    return client.post(path, data=payload)


@pytest.fixture
def as_alice(client):
    assert login(client, "alice").status_code == 302
    return client


@pytest.fixture
def as_bob(client):
    assert login(client, "bob").status_code == 302
    return client


@pytest.fixture
def as_admin(client):
    assert login(client, "admin").status_code == 302
    return client
