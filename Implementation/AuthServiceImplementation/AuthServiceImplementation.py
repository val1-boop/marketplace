"""Implementación del servicio de autenticación.

- Usuarios: RDS MySQL (`users`). Intentos y eventos: RDS PostgreSQL (`login_attempts`, `auth_events`).
- Bloqueo temporal por cuenta (HMAC del correo, exista o no la cuenta).
- Mismo trabajo de hash exista o no el usuario (anti enumeración por tiempo).
"""
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from Core.Extensions import db
from Implementation.SharedImplementation.AccountQueries import find_user_by_email, generate_seller_id
from Implementation.SharedImplementation.AuditLog import record_auth_event
from Interfaces.AuthServiceInterface.AuthDTO import PasswordChangeResult
from Interfaces.AuthServiceInterface.IAuthService import IAuthService
from Models import LoginAttempt, User, utcnow
from Security import (
    dummy_verify,
    email_hmac,
    hash_password,
    needs_rehash,
    normalize_email,
    security_log,
    verify_password,
)


class AuthServiceImplementation(IAuthService):
    def authenticate(self, email, password):
        cfg = current_app.config
        email_norm = normalize_email(email)
        key = email_hmac(email_norm)
        now = utcnow()

        # 1) ¿La cuenta está bloqueada? Se responde igual que con una contraseña mala.
        attempt = db.session.get(LoginAttempt, key)
        if attempt is not None and attempt.locked_until is not None and attempt.locked_until > now:
            dummy_verify(password)
            record_auth_event("login_locked", email_hmac_value=key)
            db.session.commit()
            security_log("login_locked", account=key.hex()[:12])
            return None

        # 2) Verificar la contraseña (o un hash falso si el correo no existe).
        user = db.session.execute(
            db.select(User).where(User.email_normalized == email_norm)
        ).scalar_one_or_none()
        if user is None:
            dummy_verify(password)
            ok = False
        else:
            ok = verify_password(user.password_hash, password) and user.status == "active"

        if ok:
            if attempt is not None:
                db.session.delete(attempt)
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
            user.last_login_at = now
            record_auth_event("login_success", user_id=user.id, email_hmac_value=key)
            db.session.commit()
            security_log("login_success", user=user.id)
            return user

        # 3) Fallo: contar y bloquear al llegar al máximo.
        window = timedelta(seconds=cfg["LOGIN_FAILURE_WINDOW_SECONDS"])
        if attempt is None:
            attempt = LoginAttempt(email_hmac=key, failures=0, updated_at=now)
            db.session.add(attempt)
        elif attempt.updated_at is None or now - attempt.updated_at > window:
            attempt.failures = 0
        attempt.failures = (attempt.failures or 0) + 1
        attempt.updated_at = now
        attempt.locked_until = None
        event = "login_failed"
        if attempt.failures >= cfg["LOGIN_MAX_FAILURES"]:
            attempt.locked_until = now + timedelta(seconds=cfg["LOGIN_LOCKOUT_SECONDS"])
            attempt.failures = 0
            event = "login_lockout"
        record_auth_event(event, user_id=user.id if user else None, email_hmac_value=key)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        security_log(event, account=key.hex()[:12])
        return None

    def register(self, data):
        email_norm = normalize_email(data.email)
        password_hash = hash_password(data.password)  # siempre se calcula: mismo tiempo en ambos casos
        if find_user_by_email(email_norm) is not None:
            security_log("register_duplicate", account=email_hmac(email_norm).hex()[:12])
            return False
        now = utcnow()
        user = User(
            email=data.email.strip(),
            email_normalized=email_norm,
            first_name=data.first_name,
            last_name=data.last_name,
            password_hash=password_hash,
            role="user",          # lo decide el servidor, nunca el formulario
            status="active",
            seller_id=generate_seller_id(),
            terms_version=current_app.config["TERMS_VERSION"],
            privacy_version=current_app.config["PRIVACY_VERSION"],
            terms_accepted_at=now,
            password_changed_at=now,
        )
        db.session.add(user)
        try:
            db.session.flush()
            record_auth_event("register", user_id=user.id, email_hmac_value=email_hmac(email_norm))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return False
        security_log("register", user=user.id)
        return True

    def logout(self, user):
        # Rotar el nonce invalida en el servidor cualquier copia de la cookie de sesión.
        user.rotate_session_nonce()
        record_auth_event("logout", user_id=user.id)
        db.session.commit()
        security_log("logout", user=user.id)

    def change_password(self, user, data):
        if not verify_password(user.password_hash, data.current_password):
            security_log("password_change_failed", user=user.id)
            return PasswordChangeResult(False, "current_password", "La contraseña actual no es correcta.")
        if data.new_password == data.current_password:
            return PasswordChangeResult(False, "new_password", "La nueva contraseña debe ser distinta.")
        user.password_hash = hash_password(data.new_password)
        user.password_changed_at = utcnow()
        user.rotate_session_nonce()  # cierra todas las sesiones abiertas
        record_auth_event("password_changed", user_id=user.id)
        db.session.commit()
        security_log("password_changed", user=user.id)
        return PasswordChangeResult(True)
