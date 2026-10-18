"""Cabeceras de seguridad, manejo de errores y límites de tamaño/host."""
from Core import create_app
from Core.Extensions import db

from .conftest import SecureClient


def test_security_headers_present(client):
    response = client.get("/auth/login")
    headers = response.headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=" in headers["Strict-Transport-Security"]
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers["Permissions-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert "Server" not in headers


def test_no_inline_scripts_in_pages(as_alice):
    for path in ["/dashboard", "/items/", "/items/PROD-001", "/items/new"]:
        body = as_alice.get(path).get_data(as_text=True)
        assert "<script>" not in body
        assert "onclick=" not in body and "onsubmit=" not in body


def test_no_cors_headers(client):
    response = client.get("/auth/login", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_404_page_is_generic(client):
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert "Traceback" not in response.get_data(as_text=True)


def test_500_page_hides_internals():
    app = create_app("testing")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.test_client_class = SecureClient

    @app.route("/__boom")
    def boom():
        raise RuntimeError("detalle-interno-secreto")

    with app.app_context():
        db.create_all()
    response = app.test_client().get("/__boom")
    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "detalle-interno-secreto" not in body
    assert "Traceback" not in body


def test_request_too_large_returns_413(client):
    response = client.post("/auth/login", data={"email": "a" * (300 * 1024), "password": "x"})
    assert response.status_code == 413


def test_untrusted_host_header_rejected(client):
    response = client.get("/auth/login", base_url="https://evil.example")
    assert response.status_code == 400


def test_debug_is_off(app):
    assert app.debug is False


def test_secret_key_required(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "corta")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost")
    try:
        create_app("production")
    except RuntimeError as error:
        assert "SECRET_KEY" in str(error)
    else:
        raise AssertionError("create_app debió fallar con una SECRET_KEY débil")
