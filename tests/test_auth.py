"""Autenticación, sesiones, registro, CSRF y open redirect."""
from Core.Extensions import db
from Models import AuthEvent, LoginAttempt, User

from .conftest import BASE_URL, EMAILS, IDS, PASSWORDS, get_csrf, login, post_form

GENERIC = "Credenciales inválidas."


# ------------------------------------------------------------------ login
def test_login_success_redirects_to_dashboard(client):
    response = login(client, "alice")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_login_wrong_password_and_unknown_email_get_same_message(client):
    r1 = login(client, "alice", password="incorrecta-123A!")
    r2 = login(client, email="nadie@marketplace.mx", password="incorrecta-123A!")
    assert r1.status_code == r2.status_code == 200
    assert GENERIC in r1.get_data(as_text=True)
    assert GENERIC in r2.get_data(as_text=True)


def test_login_empty_fields_rejected(client):
    response = login(client, email="", password="")
    assert response.status_code == 200
    assert client.get("/dashboard").status_code == 302


def test_login_sqli_payload_does_not_authenticate(client):
    for payload in ["' OR '1'='1", "admin@marketplace.mx' --", "'; DROP TABLE users;--"]:
        response = login(client, email=payload, password="' OR '1'='1")
        assert response.status_code == 200
        assert GENERIC in response.get_data(as_text=True)
    with client.application.app_context():
        assert db.session.query(User).count() == 3


def test_session_cookie_flags(client):
    response = login(client, "alice")
    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    cookies = [c for c in response.headers.getlist("Set-Cookie") if c.startswith(cookie_name + "=")]
    assert cookies, "La respuesta de login debe emitir la cookie de sesión"
    cookie = cookies[-1]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie


def test_session_is_regenerated_on_login(client):
    client.get("/auth/login")
    with client.session_transaction(base_url=BASE_URL) as sess:
        sess["planted"] = "valor-del-atacante"
    login(client, "alice")
    with client.session_transaction(base_url=BASE_URL) as sess:
        assert "planted" not in sess


def test_logout_requires_post(as_alice):
    assert as_alice.get("/auth/logout").status_code == 405


def test_logout_invalidates_old_cookie_server_side(as_alice, app):
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    stolen = as_alice.get_cookie(cookie_name).value
    response = post_form(as_alice, "/auth/logout", {}, token_path="/dashboard")
    assert response.status_code == 302
    as_alice.set_cookie(cookie_name, stolen)  # reutilizar la cookie copiada antes del logout
    response = as_alice.get("/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_lockout_after_repeated_failures(client, app):
    for _ in range(app.config["LOGIN_MAX_FAILURES"]):
        login(client, "alice", password="incorrecta-123A!")
    response = login(client, "alice")  # contraseña correcta, pero la cuenta está bloqueada
    assert response.status_code == 200
    assert GENERIC in response.get_data(as_text=True)
    assert client.get("/dashboard").status_code == 302
    with app.app_context():
        attempt = db.session.query(LoginAttempt).one()
        assert attempt.locked_until is not None
        events = {e.event for e in db.session.query(AuthEvent).all()}
        assert {"login_lockout", "login_locked"} <= events


def test_bruteforce_is_rate_limited_with_429(client):
    statuses = [login(client, "alice", password=f"intento-{i}-Aa!x").status_code for i in range(12)]
    assert 429 in statuses
    assert statuses.index(429) <= 10


def test_suspended_user_cannot_login(client, app):
    with app.app_context():
        db.session.get(User, IDS["alice"]).status = "suspended"
        db.session.commit()
    response = login(client, "alice")
    assert response.status_code == 200
    assert GENERIC in response.get_data(as_text=True)


# ------------------------------------------------------------------ open redirect
def test_next_relative_path_is_followed(client):
    response = login(client, "alice", next_url="/items/")
    assert response.headers["Location"].endswith("/items/")


def test_open_redirect_is_blocked(client):
    for evil in ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)",
                 "%2F%2Fevil.example", "/auth/logout"]:
        fresh = client.application.test_client()
        response = login(fresh, "alice", next_url=evil)
        assert response.status_code == 302
        location = response.headers["Location"]
        assert "evil" not in location
        assert location.endswith("/dashboard"), location


# ------------------------------------------------------------------ CSRF
def test_login_without_csrf_token_is_rejected(client):
    response = client.post("/auth/login", data={"email": EMAILS["alice"], "password": PASSWORDS["alice"]})
    assert response.status_code == 400


def test_post_with_forged_csrf_token_is_rejected(as_alice):
    response = as_alice.post("/items/new", data={
        "name": "Producto CSRF", "category": "computers", "price": "10", "stock": "1",
        "condition": "NEW", "csrf_token": "token-falso",
    })
    assert response.status_code == 400


def test_cross_site_referer_is_rejected(client):
    token = get_csrf(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={"email": EMAILS["alice"], "password": PASSWORDS["alice"], "csrf_token": token},
        headers={"Referer": "https://evil.example/form"},
    )
    assert response.status_code == 400


# ------------------------------------------------------------------ registro
def _register(client, **overrides):
    data = {
        "first_name": "José", "last_name": "Ñúñez Pérez", "email": "jose@correo.mx",
        "password": "Clave-Nueva-2026!", "confirm": "Clave-Nueva-2026!", "accept_terms": "y",
    }
    data.update(overrides)
    return post_form(client, "/auth/register", data)


def test_register_creates_regular_user_with_unicode_name(client, app):
    response = _register(client)
    assert response.status_code == 302
    with app.app_context():
        user = db.session.query(User).filter_by(email_normalized="jose@correo.mx").one()
        assert user.role == "user"
        assert user.seller_id and user.seller_id.startswith("SEL-")
        assert user.password_hash.startswith("$argon2id$")
        assert "Clave-Nueva-2026!" not in user.password_hash
    assert login(client, email="jose@correo.mx", password="Clave-Nueva-2026!").status_code == 302


def test_register_ignores_mass_assignment_fields(client, app):
    response = _register(client, role="admin", status="active", seller_id="SEL-999999",
                         email="masa@correo.mx")
    assert response.status_code == 302
    with app.app_context():
        user = db.session.query(User).filter_by(email_normalized="masa@correo.mx").one()
        assert user.role == "user"
        assert user.seller_id != "SEL-999999"


def test_register_rejects_weak_password(client, app):
    for weak in ["corta1!", "solominusculas", "password1234", "12345678901234"]:
        response = _register(client, password=weak, confirm=weak, email="debil@correo.mx")
        assert response.status_code == 200
    with app.app_context():
        assert db.session.query(User).filter_by(email_normalized="debil@correo.mx").count() == 0


def test_register_rejects_bad_inputs(client, app):
    cases = [
        {"confirm": "Distinta-Clave-2026!"},
        {"email": "no-es-correo"},
        {"first_name": ""},
        {"first_name": "A" * 61},
        {"first_name": "<script>alert(1)</script>"},
        {"last_name": "Robert'); DROP TABLE users;--"},
        {"accept_terms": ""},
    ]
    for case in cases:
        response = _register(client, **case)
        assert response.status_code == 200, case
    with app.app_context():
        assert db.session.query(User).count() == 3


def test_register_is_rate_limited(client, app):
    app.config["REGISTER_RATE_LIMIT"] = "2 per minute"
    statuses = [_register(client, email=f"limite{i}@correo.mx").status_code for i in range(3)]
    assert statuses[-1] == 429


def test_register_duplicate_email_does_not_reveal_or_duplicate(client, app):
    response = _register(client, email=EMAILS["alice"].upper())
    assert response.status_code == 302  # mismo flujo que un registro exitoso
    with app.app_context():
        assert db.session.query(User).filter_by(email_normalized=EMAILS["alice"]).count() == 1


# ------------------------------------------------------------------ contraseña
def test_change_password_logs_out_everywhere(as_alice, app):
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    old_cookie = as_alice.get_cookie(cookie_name).value
    response = post_form(as_alice, "/auth/password", {
        "current_password": PASSWORDS["alice"],
        "new_password": "Otra-Clave-Segura-2026?",
        "confirm": "Otra-Clave-Segura-2026?",
    })
    assert response.status_code == 302
    as_alice.set_cookie(cookie_name, old_cookie)
    assert as_alice.get("/dashboard").status_code == 302
    fresh = app.test_client()
    assert login(fresh, "alice").status_code == 200  # la contraseña anterior ya no sirve
    assert login(fresh, email=EMAILS["alice"], password="Otra-Clave-Segura-2026?").status_code == 302


def test_change_password_requires_current_password(as_alice):
    response = post_form(as_alice, "/auth/password", {
        "current_password": "incorrecta-123A!",
        "new_password": "Otra-Clave-Segura-2026?",
        "confirm": "Otra-Clave-Segura-2026?",
    })
    assert response.status_code == 200
    assert "no es correcta" in response.get_data(as_text=True)
