"""Direcciones de envío (RDS MySQL, base `marketplace`, tabla `addresses` de la Parte 5).

Columnas exactamente como en el documento. `default_owner` es una columna GENERADA por la
base (user_id solo si la dirección es la predeterminada y está activa) con índice UNIQUE:
así la base garantiza "una sola predeterminada por usuario" aunque lleguen dos peticiones
a la vez. La app nunca escribe esa columna.

Las direcciones no se borran (is_active = FALSE): los pedidos guardan su propia copia.
"""
from sqlalchemy import BigInteger, Computed, Index, Integer

from Core.Extensions import db
from Models.Common import utcnow

MAX_ADDRESSES_PER_USER = 10

# MySQL: BIGINT UNSIGNED AUTO_INCREMENT. SQLite (pruebas) solo autoincrementa INTEGER.
_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Address(db.Model):
    __tablename__ = "addresses"

    id = db.Column(_ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", name="fk_addr_user"), nullable=False)
    label = db.Column(db.String(40), nullable=False)
    recipient_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    line1 = db.Column(db.String(120), nullable=False)
    line2 = db.Column(db.String(120))
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    postal_code = db.Column(db.String(5), nullable=False)
    country = db.Column(db.String(2), nullable=False, default="MX")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    default_owner = db.Column(
        db.String(36),
        Computed("CASE WHEN is_default AND is_active THEN user_id ELSE NULL END", persisted=True),
    )

    __table_args__ = (
        db.UniqueConstraint("default_owner", name="uq_one_default"),
        Index("idx_user", "user_id", "is_active"),
    )

    def as_shipping(self):
        """La copia que viaja al pedido (lista blanca; validada otra vez en la Lambda)."""
        return {
            "recipient_name": self.recipient_name,
            "phone": self.phone,
            "line1": self.line1,
            "line2": self.line2 or "",
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
        }
