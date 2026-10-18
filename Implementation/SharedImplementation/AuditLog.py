"""Bitácoras de auditoría.

- auth_events (RDS PostgreSQL `security`): login, fallos, bloqueos, logout, registro.
- admin_actions (RDS MySQL `marketplace`): toda acción de un administrador.

Nunca se guardan contraseñas ni tokens; el correo solo como HMAC.
"""
from Core.Extensions import db
from Models import ADMIN_ACTIONS, AdminAction, AuthEvent
from Security import new_ulid, security_log


def record_auth_event(event, user_id=None, email_hmac_value=None):
    db.session.add(AuthEvent(event=event, user_id=user_id, email_hmac=email_hmac_value))


def record_admin_action(admin, action, target_type, target_id, reason):
    """Agrega la acción a la sesión de BD (quien llama hace commit). Lista blanca de acciones."""
    if action not in ADMIN_ACTIONS:
        raise ValueError("Acción administrativa no permitida")
    db.session.add(AdminAction(
        id=new_ulid(), admin_id=admin.id, action=action,
        target_type=target_type, target_id=str(target_id)[:80], reason=reason[:500],
    ))
    security_log("admin_action", admin=admin.id, action=action, target=target_id)
