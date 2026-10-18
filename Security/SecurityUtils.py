"""Utilidades de seguridad: hash de contraseñas, política, normalización,
redirecciones seguras, control de roles, escape de LIKE y bitácora de seguridad."""
import hashlib
import hmac
import logging
import re
import secrets
import time
import unicodedata
from functools import wraps
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from flask import abort, current_app, has_request_context, request
from flask_login import current_user, login_required

security_logger = logging.getLogger("marketplace.security")

# Argon2id con los parámetros por defecto de argon2-cffi (perfil RFC 9106).
_ph = PasswordHasher()
_dummy_hash = None

COMMON_PASSWORDS = {
    "password1234", "contraseña123", "contrasena123", "123456789012", "qwertyuiop12",
    "administrador", "admin1234567", "marketplace1", "iloveyou1234", "passw0rd1234",
}

PASSWORD_MIN = 12
PASSWORD_MAX = 128


# ---------------------------------------------------------------- contraseñas
def hash_password(password):
    return _ph.hash(password)


def verify_password(password_hash, password):
    """Devuelve True/False sin lanzar excepciones (hash inválido = False)."""
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash):
    try:
        return _ph.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def dummy_verify(password):
    """Iguala el tiempo de respuesta cuando el usuario no existe (anti-enumeración)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _ph.hash(secrets.token_urlsafe(24))
    verify_password(_dummy_hash, password)


def check_password_policy(password, email=None):
    """Devuelve una lista de errores; vacía si la contraseña cumple la política."""
    errors = []
    if len(password) < PASSWORD_MIN or len(password) > PASSWORD_MAX:
        errors.append(f"Debe tener entre {PASSWORD_MIN} y {PASSWORD_MAX} caracteres.")
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 3:
        errors.append("Debe combinar al menos 3 de: minúsculas, mayúsculas, números y símbolos.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Es una contraseña demasiado común.")
    if email:
        local = normalize_email(email).split("@", 1)[0]
        if len(local) >= 4 and local in password.lower():
            errors.append("No debe contener tu correo.")
    return errors


# ------------------------------------------------------------- normalización
def normalize_text(value):
    return unicodedata.normalize("NFC", value).strip() if isinstance(value, str) else value


def normalize_email(value):
    return unicodedata.normalize("NFKC", value or "").strip().lower()


def normalize_search(value):
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def email_hmac(email_normalized):
    key = current_app.config["LOGIN_HMAC_KEY"].encode("utf-8")
    return hmac.new(key, email_normalized.encode("utf-8"), hashlib.sha256).digest()


def escape_like(value):
    """Escapa los comodines de LIKE para que se busquen literalmente (usar escape='\\')."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ------------------------------------------------------------- redirecciones
_BLOCKED_NEXT_PREFIXES = ("/auth/logout",)


def is_safe_redirect(target):
    """Solo permite rutas relativas del propio sitio (anti open redirect)."""
    if not target or not isinstance(target, str) or len(target) > 512:
        return False
    if any(ord(c) < 32 or c == "\\" for c in target):
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return False
    return not parts.path.startswith(_BLOCKED_NEXT_PREFIXES)


# ---------------------------------------------------------------------- roles
def role_required(*roles):
    """Exige sesión (via login_required) y uno de los roles indicados; si no, 403."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                security_log("access_denied", user=current_user.id, required="|".join(roles))
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------------------------------------------------ ID / ULID
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid():
    """ULID de 26 caracteres (48 bits de tiempo + 80 aleatorios), como admin_actions.id."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(secrets.token_bytes(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


PRODUCT_ID_RE = re.compile(r"^PROD-[0-9]{3,8}\Z")
SELLER_ID_RE = re.compile(r"^SEL-[0-9]{3,8}\Z")


# ------------------------------------------------------------------ bitácora
def _clean(value):
    """Neutraliza saltos de línea y caracteres de control (anti log injection)."""
    return str(value).encode("unicode_escape").decode("ascii")[:200]


def security_log(event, **fields):
    """Registra un evento de seguridad. Nunca recibe contraseñas ni tokens."""
    ip = request.remote_addr if has_request_context() else "-"
    path = request.path if has_request_context() else "-"
    extra = " ".join(f"{k}={_clean(v)}" for k, v in fields.items())
    security_logger.warning("event=%s ip=%s path=%s %s", _clean(event), _clean(ip), _clean(path), extra)
