"""Perfil público de la tienda de cada vendedor (RDS MySQL, base `marketplace`, tabla `sellers`).

Es la entidad "Vendedores" del proyecto: el código de vendedor (`seller_id`) sigue viviendo en
`users`, y aquí se guarda lo que la persona quiere mostrar de su tienda (nombre y descripción).
"""
from Core.Extensions import db
from Models.Common import utcnow


class Seller(db.Model):
    __tablename__ = "sellers"

    seller_id = db.Column(db.String(20), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", name="fk_seller_user"), nullable=False, unique=True)
    store_name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
