"""Consultas de cuentas que usan varios servicios (RDS MySQL, tabla users).

Todas pasan por el ORM de SQLAlchemy: los valores viajan como parámetros, nunca
concatenados en el SQL (sin inyección).
"""
import secrets

from Core.Extensions import db
from Models import Seller, User
from Security import normalize_email


def find_user_by_email(email):
    return db.session.execute(
        db.select(User).where(User.email_normalized == normalize_email(email))
    ).scalar_one_or_none()


def generate_seller_id():
    """SEL- + 6 dígitos al azar (secrets, no random), sin repetir uno existente."""
    for _ in range(20):
        candidate = f"SEL-{secrets.randbelow(10**6):06d}"
        exists = db.session.execute(db.select(User.id).where(User.seller_id == candidate)).first()
        if not exists:
            return candidate
    raise RuntimeError("No fue posible generar un seller_id único")


def active_admin_count():
    return db.session.scalar(
        db.select(db.func.count()).select_from(User)
        .where(User.role.in_(("admin", "super_admin")), User.status == "active")
    )


def seller_display_names(seller_ids):
    """Nombre público de cada vendedor: el de su tienda si lo configuró; si no, nombre + inicial
    del apellido (nunca el correo)."""
    ids = {sid for sid in seller_ids if sid}
    if not ids:
        return {}
    rows = db.session.execute(
        db.select(User.seller_id, User.first_name, User.last_name, Seller.store_name)
        .outerjoin(Seller, Seller.seller_id == User.seller_id)
        .where(User.seller_id.in_(ids), User.status == "active")
    ).all()
    return {sid: (store or f"{first} {last[:1]}.") for sid, first, last, store in rows}


def user_id_of_seller(seller_id):
    """id de la cuenta dueña de una tienda (solo se usa en vistas de administrador)."""
    if not seller_id:
        return None
    return db.session.execute(db.select(User.id).where(User.seller_id == seller_id)).scalar_one_or_none()
