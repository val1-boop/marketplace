"""Modelos de la base `marketplace` (RDS MySQL, bind por defecto): users y admin_actions.

Nombres de tablas y columnas según la Parte 5 del documento. Adición al documento:
users.session_nonce, para invalidar sesiones del lado del servidor.
Los productos NO están aquí: viven en DynamoDB (tabla Products) y se manejan con
Implementation/ProductServiceImplementation/ProductsApiClient.py.

Las enumeraciones se implementan con CHECK para que el esquema sea portable entre
SQLite (pruebas) y MySQL.
"""
import hmac
import secrets
import uuid

from flask_login import AnonymousUserMixin, UserMixin
from sqlalchemy import CheckConstraint, Index

from Core.Extensions import db, login_manager
from Models.Common import sql_in, utcnow

ROLES = ("user", "admin", "super_admin")
USER_STATUSES = ("active", "suspended", "banned", "deleted")


def _new_nonce():
    return secrets.token_hex(16)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(254), nullable=False)
    email_normalized = db.Column(db.String(254), nullable=False, unique=True)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="user")
    status = db.Column(db.String(16), nullable=False, default="active")
    status_reason = db.Column(db.String(500))
    seller_id = db.Column(db.String(20), unique=True)
    email_verified_at = db.Column(db.DateTime)
    terms_version = db.Column(db.String(10), nullable=False)
    privacy_version = db.Column(db.String(10), nullable=False)
    terms_accepted_at = db.Column(db.DateTime, nullable=False)
    last_login_at = db.Column(db.DateTime)
    password_changed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    deleted_at = db.Column(db.DateTime)
    session_nonce = db.Column(db.String(64), nullable=False, default=_new_nonce)

    __table_args__ = (
        CheckConstraint(sql_in("role", ROLES), name="chk_users_role"),
        CheckConstraint(sql_in("status", USER_STATUSES), name="chk_users_status"),
        CheckConstraint("role = 'user' OR seller_id IS NULL", name="chk_staff_no_store"),
        Index("idx_role_status", "role", "status"),
    )

    # Flask-Login: el identificador de sesión incluye el nonce, así que rotarlo
    # invalida cualquier cookie emitida antes (logout, cambio de contraseña o de rol).
    def get_id(self):
        return f"{self.id}:{self.session_nonce}"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def is_admin(self):
        return self.role in ("admin", "super_admin")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def rotate_session_nonce(self):
        self.session_nonce = _new_nonce()


class AnonymousUser(AnonymousUserMixin):
    """Visitante sin sesión (el catálogo es público). Tiene los mismos atributos que
    User con valores seguros, para que ninguna comprobación de dueño o de rol falle
    con AttributeError ni conceda permisos por accidente."""

    id = None
    role = None
    seller_id = None
    first_name = ""
    is_admin = False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(token):
    if not isinstance(token, str) or ":" not in token:
        return None
    user_id, nonce = token.split(":", 1)
    if len(user_id) != 36:
        return None
    user = db.session.get(User, user_id)
    if user is None or user.status != "active" or not user.session_nonce:
        return None
    if not hmac.compare_digest(user.session_nonce, nonce):
        return None
    return user


ADMIN_ACTIONS = (
    "block_product", "unblock_product", "delete_product",
    "create_user", "update_user", "delete_user",
    "suspend_user", "ban_user", "reactivate_user", "grant_admin", "revoke_admin",
)


class AdminAction(db.Model):
    __tablename__ = "admin_actions"

    id = db.Column(db.String(26), primary_key=True)
    admin_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(32), nullable=False)
    target_type = db.Column(db.String(16), nullable=False)
    target_id = db.Column(db.String(80), nullable=False)
    report_id = db.Column(db.String(26))
    reason = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(sql_in("action", ADMIN_ACTIONS), name="chk_admin_actions_action"),
        CheckConstraint(sql_in("target_type", ("product", "user")), name="chk_admin_actions_target"),
        Index("idx_admin_time", "admin_id", "created_at"),
        Index("idx_target", "target_type", "target_id", "created_at"),
    )
