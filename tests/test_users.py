"""CRUD de usuarios (solo admin)."""
from Core.Extensions import db
from Models import AdminAction, User

from .conftest import IDS, login, post_form

NEW_USER = {"first_name": "Valeria", "last_name": "Lagunas", "email": "valeria@marketplace.mx",
            "role": "user", "password": "Clave-Segura-Nueva-2026!", "confirm": "Clave-Segura-Nueva-2026!"}


def _edit_data(**overrides):
    data = {"first_name": "Alice", "last_name": "Prueba", "email": "alice@marketplace.mx",
            "role": "user", "status": "active", "status_reason": "", "new_password": "", "confirm": ""}
    data.update(overrides)
    return data


def test_admin_lists_and_searches_users(as_admin):
    body = as_admin.get("/users/").get_data(as_text=True)
    assert "alice@marketplace.mx" in body and "bob@marketplace.mx" in body
    body = as_admin.get("/users/", query_string={"q": "alice"}).get_data(as_text=True)
    assert "alice@marketplace.mx" in body and "bob@marketplace.mx" not in body


def test_admin_user_search_injection_and_wildcards(as_admin):
    for q in ["' OR '1'='1", "%", "_", "<script>alert(1)</script>"]:
        response = as_admin.get("/users/", query_string={"q": q})
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "alice@marketplace.mx" not in body
        assert "<script>alert(1)</script>" not in body


def test_admin_creates_user(as_admin, app):
    response = post_form(as_admin, "/users/new", NEW_USER)
    assert response.status_code == 302
    with app.app_context():
        user = db.session.query(User).filter_by(email_normalized="valeria@marketplace.mx").one()
        assert user.role == "user" and user.seller_id
        assert db.session.query(AdminAction).filter_by(action="create_user").count() == 1


def test_admin_create_user_rejects_weak_password_and_duplicate(as_admin, app):
    weak = dict(NEW_USER, password="debil", confirm="debil")
    assert post_form(as_admin, "/users/new", weak).status_code == 200
    duplicate = dict(NEW_USER, email="ALICE@marketplace.mx")
    assert post_form(as_admin, "/users/new", duplicate).status_code == 200
    with app.app_context():
        assert db.session.query(User).count() == 3


def test_admin_create_rejects_unknown_role(as_admin, app):
    response = post_form(as_admin, "/users/new", dict(NEW_USER, role="super_admin"))
    assert response.status_code == 200
    with app.app_context():
        assert db.session.query(User).count() == 3


def test_admin_views_and_edits_user(as_admin, app):
    assert as_admin.get(f"/users/{IDS['alice']}").status_code == 200
    response = post_form(as_admin, f"/users/{IDS['alice']}/edit", _edit_data(first_name="Alicia"))
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, IDS["alice"]).first_name == "Alicia"


def test_admin_suspends_user_and_session_dies(client, app):
    victim = app.test_client()
    login(victim, "alice")
    assert victim.get("/dashboard").status_code == 200
    login(client, "admin")
    response = post_form(client, f"/users/{IDS['alice']}/edit",
                         _edit_data(status="suspended", status_reason="Revisión"))
    assert response.status_code == 302
    assert victim.get("/dashboard").status_code == 302


def test_admin_cannot_demote_or_suspend_self(as_admin, app):
    data = {"first_name": "Admin", "last_name": "Prueba", "email": "admin@marketplace.mx",
            "role": "user", "status": "active"}
    response = post_form(as_admin, f"/users/{IDS['admin']}/edit", data)
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(User, IDS["admin"]).role == "admin"


def test_cannot_promote_user_with_products_to_admin(as_admin, app):
    response = post_form(as_admin, f"/users/{IDS['alice']}/edit", _edit_data(role="admin"))
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(User, IDS["alice"]).role == "user"


def test_admin_resets_password_with_policy(as_admin, app):
    weak = _edit_data(new_password="corta", confirm="corta")
    assert post_form(as_admin, f"/users/{IDS['alice']}/edit", weak).status_code == 200
    strong = _edit_data(new_password="Nueva-Clave-Segura-2026!", confirm="Nueva-Clave-Segura-2026!")
    assert post_form(as_admin, f"/users/{IDS['alice']}/edit", strong).status_code == 302
    fresh = app.test_client()
    assert login(fresh, email="alice@marketplace.mx", password="Nueva-Clave-Segura-2026!").status_code == 302


def test_admin_deletes_user(as_admin, app, table):
    response = post_form(as_admin, f"/users/{IDS['alice']}/delete", {}, token_path=f"/users/{IDS['alice']}")
    assert response.status_code == 302
    with app.app_context():
        user = db.session.get(User, IDS["alice"])
        assert user.status == "deleted"
        assert "alice" not in user.email
    assert table.items["PROD-001"]["status"] == "DELISTED"
    assert as_admin.get(f"/users/{IDS['alice']}").status_code == 404
    fresh = app.test_client()
    assert login(fresh, "alice").status_code == 200  # ya no puede entrar
    assert fresh.get("/dashboard").status_code == 302


def test_admin_cannot_delete_self(as_admin, app):
    response = post_form(as_admin, f"/users/{IDS['admin']}/delete", {}, token_path=f"/users/{IDS['admin']}")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, IDS["admin"]).status == "active"


def test_unknown_or_malformed_user_id(as_admin):
    assert as_admin.get("/users/00000000-0000-4000-8000-00000000ffff").status_code == 404
    assert as_admin.get("/users/1").status_code == 404
    assert as_admin.get("/users/../etc/passwd").status_code == 404
