"""Implementación del servicio de usuarios (solo administradores; RDS MySQL `users`).

Reglas: nadie cambia su propio rol o estado, nadie se borra a sí mismo, siempre queda
al menos un administrador activo y un administrador no tiene tienda. Cada cambio se
registra en admin_actions.
"""
import secrets

from Core.Extensions import db
from Implementation.SharedImplementation.AccountQueries import (
    active_admin_count,
    find_user_by_email,
    generate_seller_id,
)
from Implementation.SharedImplementation.AuditLog import record_admin_action
from Interfaces.UserServiceInterface.IUserService import IUserService
from Interfaces.UserServiceInterface.UserDTO import UserResult
from Models import User, utcnow
from Security import escape_like, hash_password, normalize_email, normalize_search

STATUS_ACTIONS = {"active": "reactivate_user", "suspended": "suspend_user", "banned": "ban_user"}
USER_PRODUCTS_LIMIT = 20


class UserServiceImplementation(IUserService):
    def __init__(self, product_service):
        self.products = product_service

    def search_users(self, q, page, per_page):
        stmt = db.select(User).where(User.status != "deleted")
        if q:
            # LIKE parametrizado; escape_like hace que % y _ se busquen como texto.
            term = f"%{escape_like(normalize_search(q))}%"
            stmt = stmt.where(db.or_(
                User.email_normalized.like(term, escape="\\"),
                db.func.lower(User.first_name).like(term, escape="\\"),
                db.func.lower(User.last_name).like(term, escape="\\"),
            ))
        return db.paginate(stmt.order_by(User.created_at.desc()), page=page,
                           per_page=per_page, max_per_page=per_page, error_out=False)

    def empty_search(self, page, per_page):
        """Búsqueda inválida (p. ej. caracteres de control): ningún resultado."""
        return db.paginate(db.select(User).where(db.false()), page=page,
                           per_page=per_page, max_per_page=per_page, error_out=False)

    def get_user(self, user_id):
        user = db.session.get(User, str(user_id))
        if user is None or user.status == "deleted":
            return None
        return user

    def user_products(self, user):
        if not user.seller_id:
            return []
        return sorted(self.products.api.list_products(seller_id=user.seller_id),
                      key=lambda p: p.updated_at, reverse=True)[:USER_PRODUCTS_LIMIT]

    def create_user(self, admin, data):
        if find_user_by_email(data.email) is not None:
            return UserResult(error="Ese correo ya está registrado.", field="email")
        now = utcnow()
        user = User(
            email=data.email,
            email_normalized=normalize_email(data.email),
            first_name=data.first_name,
            last_name=data.last_name,
            password_hash=hash_password(data.password),
            role=data.role,
            status="active",
            seller_id=generate_seller_id() if data.role == "user" else None,
            terms_version="admin",
            privacy_version="admin",
            terms_accepted_at=now,
            password_changed_at=now,
        )
        db.session.add(user)
        db.session.flush()
        record_admin_action(admin, "create_user", "user", user.id, f"Alta con rol {data.role}")
        db.session.commit()
        return UserResult(user=user)

    def update_user(self, admin, user, data):
        is_self = user.id == admin.id
        role_changed = data.role != user.role
        status_changed = data.status != user.status
        new_email = normalize_email(data.email)
        email_changed = new_email != user.email_normalized

        if is_self and (role_changed or status_changed):
            return UserResult(error="No puedes cambiar tu propio rol ni tu propio estado.")
        if user.is_admin and (data.role != "admin" or data.status != "active") and active_admin_count() <= 1:
            return UserResult(error="Debe quedar al menos un administrador activo.")
        if role_changed and data.role == "admin" and self.products.owns_listed_products(user.seller_id):
            return UserResult(error="El usuario tiene productos publicados; elimínalos antes de hacerlo administrador.")
        if email_changed and find_user_by_email(new_email) is not None:
            return UserResult(error="Revisa los campos marcados.", field="email")

        # Asignación explícita campo por campo (sin mass assignment).
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.email = data.email
        user.email_normalized = new_email
        user.status_reason = data.status_reason or None
        if role_changed:
            if data.role == "admin":
                user.seller_id = None
                record_admin_action(admin, "grant_admin", "user", user.id, "Cambio de rol")
            else:
                user.seller_id = user.seller_id or generate_seller_id()
                record_admin_action(admin, "revoke_admin", "user", user.id, "Cambio de rol")
            user.role = data.role
        if status_changed:
            record_admin_action(admin, STATUS_ACTIONS[data.status], "user", user.id,
                                data.status_reason or "Cambio de estado")
            user.status = data.status
        password_changed = bool(data.new_password)
        if password_changed:
            user.password_hash = hash_password(data.new_password)
            user.password_changed_at = utcnow()
        if role_changed or status_changed or email_changed or password_changed:
            user.rotate_session_nonce()  # obliga a esa persona a iniciar sesión de nuevo
        record_admin_action(admin, "update_user", "user", user.id, "Edición de datos")
        db.session.commit()
        return UserResult(user=user)

    def delete_user(self, admin, user):
        if user.id == admin.id:
            return "No puedes eliminar tu propia cuenta."
        if user.is_admin and active_admin_count() <= 1:
            return "Debe quedar al menos un administrador activo."
        # Borrado lógico: se anonimiza la cuenta, se invalida la sesión y se retiran sus productos.
        if user.seller_id:
            self.products.delist_seller_products(user.seller_id)
        user.status = "deleted"
        user.deleted_at = utcnow()
        user.email = f"deleted-{user.id}@deleted.invalid"
        user.email_normalized = user.email
        user.first_name = "Usuario"
        user.last_name = "eliminado"
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.rotate_session_nonce()
        record_admin_action(admin, "delete_user", "user", user.id, "Baja de usuario")
        db.session.commit()
        return ""
