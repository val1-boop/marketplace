"""Configuración por entorno.

Todos los secretos se leen de variables de entorno (nunca se escriben en el código).
Se construye un diccionario en tiempo de ejecución para que `load_dotenv()` ya se haya
ejecutado cuando se lean las variables.
"""
import os
import secrets
from datetime import timedelta

VALID_ENVS = {"development", "production", "testing"}


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int(name, default):
    value = os.environ.get(name)
    if value is None or not value.strip().isdigit():
        return default
    return int(value)


def get_config(env_name):
    if env_name not in VALID_ENVS:
        raise ValueError(f"APP_ENV inválido: {env_name!r}")

    cfg = dict(
        DEBUG=False,
        TESTING=False,
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        # Clave para el HMAC de correos en login_attempts / auth_events.
        # Si no se define, se deriva de SECRET_KEY en create_app().
        LOGIN_HMAC_KEY=os.environ.get("LOGIN_HMAC_KEY", ""),
        # Base principal (users, admin_actions): RDS MySQL `marketplace` (Parte 5).
        # Si no hay DATABASE_URL, create_app() usa SQLite en instance/.
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", ""),
        # Base de seguridad (login_attempts, auth_events): RDS PostgreSQL `security`.
        SECURITY_DATABASE_URL=os.environ.get("SECURITY_DATABASE_URL", ""),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        # --- API de productos (API Gateway → Lambda → DynamoDB Products) ---
        PRODUCTS_API_URL=os.environ.get("PRODUCTS_API_URL", ""),
        PRODUCTS_API_TOKEN=os.environ.get("PRODUCTS_API_TOKEN", ""),
        PRODUCTS_API_TIMEOUT=(3.05, 10),
        # Caché corta del listado de productos: el catálogo es público y así muchas visitas
        # no se convierten en muchas llamadas a Lambda/DynamoDB (se vacía al escribir).
        PRODUCT_LIST_CACHE_SECONDS=_env_int("PRODUCT_LIST_CACHE_SECONDS", 10),
        # --- Sesión ---
        SESSION_COOKIE_NAME="__Host-mkt_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=_env_int("SESSION_IDLE_MINUTES", 30)),
        SESSION_REFRESH_EACH_REQUEST=True,
        ABSOLUTE_SESSION_SECONDS=_env_int("SESSION_ABSOLUTE_HOURS", 8) * 3600,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_SAMESITE="Strict",
        # --- Límites de tamaño (mitigación DoS) ---
        MAX_CONTENT_LENGTH=256 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024,
        MAX_FORM_PARTS=100,
        # --- CSRF ---
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=3600,
        WTF_CSRF_SSL_STRICT=True,
        # --- Rate limiting ---
        RATELIMIT_ENABLED=True,
        RATELIMIT_STORAGE_URI=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        RATELIMIT_DEFAULT="300 per minute",
        RATELIMIT_HEADERS_ENABLED=True,
        LOGIN_RATE_LIMIT="10 per minute;50 per hour",
        REGISTER_RATE_LIMIT="5 per minute;20 per hour",
        CREDENTIAL_CHANGE_RATE_LIMIT="5 per minute;20 per hour",
        SEARCH_RATE_LIMIT="60 per minute",
        # Tienda (cada escritura es una llamada a Lambda/DynamoDB: se limita por usuario).
        CART_RATE_LIMIT="30 per minute",
        CHECKOUT_RATE_LIMIT="10 per minute;30 per hour",
        ORDER_STATUS_RATE_LIMIT="20 per minute",
        REVIEW_RATE_LIMIT="5 per minute;20 per hour",
        ADDRESS_RATE_LIMIT="20 per minute",
        # --- Bloqueo por intentos fallidos ---
        LOGIN_MAX_FAILURES=5,
        LOGIN_FAILURE_WINDOW_SECONDS=900,
        LOGIN_LOCKOUT_SECONDS=900,
        # --- Transporte / proxy ---
        FORCE_HTTPS=True,
        PREFERRED_URL_SCHEME="https",
        TRUSTED_HOSTS=_env_list("ALLOWED_HOSTS", None),
        PROXY_FIX_COUNT=_env_int("TRUSTED_PROXY_COUNT", 0),
        # --- Versiones de términos (tabla users) ---
        TERMS_VERSION="2026-10",
        PRIVACY_VERSION="2026-10",
    )

    if env_name == "development":
        secure = _env_bool("SESSION_COOKIE_SECURE", True)
        cfg.update(
            # El prefijo __Host- exige HTTPS; en local se usa un nombre normal.
            SESSION_COOKIE_NAME="mkt_session",
            SESSION_COOKIE_SECURE=secure,
            REMEMBER_COOKIE_SECURE=secure,
            FORCE_HTTPS=False,
            TRUSTED_HOSTS=_env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1"]),
        )
    elif env_name == "testing":
        cfg.update(
            TESTING=True,
            SECRET_KEY=secrets.token_urlsafe(48),
            LOGIN_HMAC_KEY=secrets.token_urlsafe(32),
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SECURITY_DATABASE_URL="sqlite://",
            # Las pruebas sustituyen el transporte por un API Gateway simulado.
            PRODUCTS_API_URL="https://pruebas.execute-api.us-east-1.amazonaws.com",
            PRODUCTS_API_TOKEN=secrets.token_urlsafe(48),
            RATELIMIT_STORAGE_URI="memory://",
            FORCE_HTTPS=False,
            TRUSTED_HOSTS=["localhost"],
            # Más holgado para que las pruebas de validación no choquen con el límite;
            # test_register_is_rate_limited lo reduce para comprobar el 429.
            REGISTER_RATE_LIMIT="30 per minute",
            # Sin caché: cada prueba ve al instante lo que cambia en el DynamoDB simulado.
            PRODUCT_LIST_CACHE_SECONDS=0,
        )
    return cfg
