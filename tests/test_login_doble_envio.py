"""Enviar dos veces el formulario de acceso (doble clic o Enter + clic) no debe mostrar un error 400.

El primer envío inicia sesión y renueva la sesión (y con ella el token CSRF); el segundo llega con el token
anterior. Antes mostraba "La solicitud no es válida"; ahora la persona, que ya entró, va a su panel.
"""
from .conftest import EMAILS, PASSWORDS, get_csrf


def _login_data(client, who="bob"):
    return {"email": EMAILS[who], "password": PASSWORDS[who], "csrf_token": get_csrf(client, "/auth/login")}


def test_double_submit_of_login_goes_to_the_dashboard(client):
    data = _login_data(client)
    first = client.post("/auth/login", data=data)
    second = client.post("/auth/login", data=data)        # el mismo formulario, otra vez
    assert first.status_code == 302 and first.headers["Location"].endswith("/dashboard")
    assert second.status_code == 302 and second.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200    # la sesión sigue activa


def test_the_greeting_is_shown_once_after_the_double_submit(client):
    data = _login_data(client)
    client.post("/auth/login", data=data)
    client.post("/auth/login", data=data)
    page = client.get(client.post("/auth/login", data=data).headers["Location"]).get_data(as_text=True)
    assert "Hola, Bob" in page and "La solicitud no es válida" not in page


def test_anonymous_post_with_a_bad_token_is_still_rejected(client):
    response = client.post("/auth/login", data={"email": EMAILS["bob"], "password": PASSWORDS["bob"],
                                                "csrf_token": "token-falso"})
    assert response.status_code == 400 and "La solicitud no es válida" in response.get_data(as_text=True)
    assert client.get("/dashboard").status_code == 302     # no inició sesión


def test_other_forms_with_a_bad_token_are_still_rejected_when_logged_in(as_bob):
    response = as_bob.post("/cart/add/PROD-001", data={"quantity": "1", "csrf_token": "token-falso"})
    assert response.status_code == 400


def test_login_with_a_bad_password_still_fails(client):
    data = _login_data(client)
    data["password"] = "Clave-Incorrecta-2026!"
    response = client.post("/auth/login", data=data)
    assert response.status_code == 200 and "dashboard" not in response.headers.get("Location", "")
