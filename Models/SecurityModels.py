"""Modelos de la base `security` (RDS PostgreSQL, bind "security"): login_attempts y auth_events.

Se guardan aparte de las cuentas, con su propio usuario de base de datos, para aislar
el rastro de seguridad (Parte 5 del documento).
"""
from sqlalchemy import BigInteger, Index, Integer

from Core.Extensions import db
from Models.Common import utcnow


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    __bind_key__ = "security"

    email_hmac = db.Column(db.LargeBinary(32), primary_key=True)
    failures = db.Column(db.SmallInteger, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class AuthEvent(db.Model):
    __tablename__ = "auth_events"
    __bind_key__ = "security"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event = db.Column(db.String(32), nullable=False)
    user_id = db.Column(db.String(36))
    email_hmac = db.Column(db.LargeBinary(32))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_user_time", "user_id", "created_at"),
        Index("idx_time", "created_at"),
    )
