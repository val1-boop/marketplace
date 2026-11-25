"""Application Factory del marketplace: arma Flask, la seguridad y las capas del proyecto.

Estructura (pedida por el profesor):
    Services/        rutas de cada módulo (la puerta de entrada de cada servicio)
    Interfaces/      contrato de cada servicio (clase abstracta) y sus DTO
    Implementation/  lógica y acceso a datos (RDS por SQLAlchemy, DynamoDB por API Gateway)
    View/            presentación de cada módulo: PY (formularios), HTML, CSS, JS, Utils
    Core/ Models/ Security/   configuración, modelos SQL y utilidades de seguridad
"""
import hashlib
import hmac
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from jinja2 import FileSystemLoader
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from Core.Config import get_config
from Core.Extensions import csrf, db, limiter, login_manager, migrate, talisman
from Security import security_log

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEW_ROOT = PROJECT_ROOT / "View"
UNTRACKED_ENDPOINTS = {"assets"}  # archivos CSS/JS/fuentes: sin hooks de sesión

CSP = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self'",
    "img-src": "'self' data:",
    "font-src": "'self'",
    "connect-src": "'self'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
    "frame-ancestors": "'none'",
}

PERMISSIONS_POLICY = {
    "geolocation": "()",
    "camera": "()",
    "microphone": "()",
    "payment": "()",
    "usb": "()",
    "browsing-topics": "()",
}

ERROR_MESSAGES = {
    400: "La solicitud no es válida.",
    401: "Necesitas iniciar sesión.",
    403: "No tienes permiso para acceder a este recurso.",
    404: "El recurso solicitado no existe.",
    405: "Método no permitido.",
    413: "La solicitud es demasiado grande.",
    503: "La tienda no está disponible en este momento. Intenta de nuevo en unos minutos.",
    429: "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
    500: "Ocurrió un error interno. Intenta más tarde.",
}


def create_app(config_name=None):
    load_dotenv()
    config_name = config_name or os.environ.get("APP_ENV", "production")

    # Sin carpeta static global: cada vista publica solo su CSS/JS (View/SharedViews/Utils/Assets.py).
    app = Flask(__name__, static_folder=None, template_folder=None,
                instance_path=str(PROJECT_ROOT / "instance"))
    app.config.from_mapping(get_config(config_name))
    app.config["APP_ENV"] = config_name
    # Las plantillas se buscan dentro de View/: "ProductViews/HTML/Catalog.html".
    app.jinja_loader = FileSystemLoader(str(VIEW_ROOT))

    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        os.makedirs(app.instance_path, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "marketplace.db")
    if not app.config["SECURITY_DATABASE_URL"]:
        os.makedirs(app.instance_path, exist_ok=True)
        app.config["SECURITY_DATABASE_URL"] = "sqlite:///" + os.path.join(app.instance_path, "security.db")
    # login_attempts y auth_events viven en otra base (RDS PostgreSQL `security`).
    app.config["SQLALCHEMY_BINDS"] = {"security": app.config["SECURITY_DATABASE_URL"]}

    _validate_config(app)

    if app.config["PROXY_FIX_COUNT"] > 0:
        n = app.config["PROXY_FIX_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n)

    _configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para continuar."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    talisman.init_app(
        app,
        force_https=app.config["FORCE_HTTPS"],
        force_https_permanent=False,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        content_security_policy=CSP,
        frame_options="DENY",
        referrer_policy="strict-origin-when-cross-origin",
        permissions_policy=PERMISSIONS_POLICY,
        # Talisman reescribe estas opciones de la cookie; se le pasan las de la config
        # para que no las cambie (por defecto pondría SameSite=Lax).
        session_cookie_secure=app.config["SESSION_COOKIE_SECURE"],
        session_cookie_http_only=True,
        session_cookie_samesite=app.config["SESSION_COOKIE_SAMESITE"],
    )

    import Models  # noqa: F401  (registra los modelos y el user_loader)
    from Core.ServiceRegistry import build_services
    from Implementation.ProductServiceImplementation.ProductsApiClient import ProductsAPI
    from Services.AddressService.AddressService import bp as addresses_bp
    from Services.AuthService.AuthService import bp as auth_bp
    from Services.CartService.CartService import bp as cart_bp
    from Services.FavoriteService.FavoriteService import bp as favorites_bp
    from Services.MainService.MainService import bp as main_bp
    from Services.OrderService.OrderService import bp as orders_bp
    from Services.ProductService.ProductService import bp as items_bp
    from Services.ReviewService.ReviewService import bp as reviews_bp
    from Services.UserService.UserService import bp as users_bp
    from View.SharedViews.Utils.Assets import register_assets
    from View.SharedViews.Utils.TemplateHelpers import register_template_helpers

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(addresses_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(reviews_bp)
    register_assets(app)

    # Un solo cliente HTTP del API (las pruebas lo sustituyen por un API Gateway simulado)
    # y una instancia de cada servicio.
    app.extensions["products_api"] = ProductsAPI(
        app.config["PRODUCTS_API_URL"], app.config["PRODUCTS_API_TOKEN"],
        timeout=app.config["PRODUCTS_API_TIMEOUT"],
    )
    app.extensions["services"] = build_services()

    register_template_helpers(app)
    _register_hooks(app)
    _register_login_redirect(app)
    _register_error_handlers(app)

    from Core.Cli import register_cli
    register_cli(app)

    return app


def _validate_config(app):
    """Si la configuración es insegura, la app NO arranca (falla cerrada)."""
    secret = app.config.get("SECRET_KEY") or ""
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY debe definirse en el entorno con al menos 32 caracteres aleatorios.")
    if not app.config.get("LOGIN_HMAC_KEY"):
        app.config["LOGIN_HMAC_KEY"] = hmac.new(
            secret.encode("utf-8"), b"login-attempts-email-hmac", hashlib.sha256
        ).hexdigest()
    api_url = app.config.get("PRODUCTS_API_URL") or ""
    if not api_url.startswith("https://"):
        raise RuntimeError("PRODUCTS_API_URL debe ser la URL https:// del API Gateway.")
    if len(app.config.get("PRODUCTS_API_TOKEN") or "") < 32:
        raise RuntimeError(
            "PRODUCTS_API_TOKEN debe tener al menos 32 caracteres (igual que API_TOKEN del autorizador)."
        )
    if app.config["APP_ENV"] == "production":
        if app.debug:
            raise RuntimeError("Nunca ejecutar con debug en producción.")
        if not app.config.get("TRUSTED_HOSTS"):
            raise RuntimeError("Define ALLOWED_HOSTS en producción (protección de cabecera Host).")
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("SESSION_COOKIE_SECURE debe ser True en producción.")


def _configure_logging(app):
    logger = logging.getLogger("marketplace.security")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _register_hooks(app):
    @app.before_request
    def enforce_absolute_session_timeout():
        if request.endpoint in UNTRACKED_ENDPOINTS:
            return None
        if current_user.is_authenticated:
            auth_at = session.get("auth_at")
            if not isinstance(auth_at, int) or time.time() - auth_at > app.config["ABSOLUTE_SESSION_SECONDS"]:
                logout_user()
                session.clear()
                flash("Tu sesión expiró. Inicia sesión de nuevo.", "info")
                return redirect(url_for("auth.login"))
        return None

    @app.before_request
    def sync_shop_counters():
        """Una vez por sesión: número de piezas del carrito y favoritos (solo para pintar el
        contador y los corazones). Si el API no responde, la página se muestra igual."""
        if request.endpoint in UNTRACKED_ENDPOINTS or request.method != "GET":
            return None
        if current_user.is_authenticated and current_user.role == "user" and not session.get("shop_synced"):
            from Core.ServiceRegistry import cart_service
            cart_service().refresh_counters(current_user, session)
        return None

    @app.after_request
    def security_headers(response):
        if request.endpoint not in UNTRACKED_ENDPOINTS:
            # Evita que páginas con sesión queden en caché (botón "atrás" tras logout).
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.pop("Server", None)
        return response


def _render_error(code):
    message = ERROR_MESSAGES.get(code, ERROR_MESSAGES[500])
    try:
        return render_template("SharedViews/HTML/Error.html", code=code, message=message), code
    except Exception:  # p. ej. Host no confiable: no hay url_adapter para url_for
        return f"Error {code}: {message}", code, {"Content-Type": "text/plain; charset=utf-8"}


def _register_login_redirect(app):
    """Sin sesión, la persona va al login y, al entrar, regresa a donde estaba.

    Una página (GET) se recuerda tal cual. Una acción (POST: agregar al carrito, favoritos, reseñar…)
    solo admite POST, así que volver a su dirección daría un 405: se regresa a la página de origen
    (la ficha del producto), que es lo que hace un marketplace."""
    from flask_login.utils import login_url

    from Security import is_safe_redirect
    from View.SharedViews.PY.SafeNext import origin_page

    @login_manager.unauthorized_handler
    def to_login():
        flash(login_manager.login_message, login_manager.login_message_category)
        target = request.full_path.rstrip("?") if request.method in ("GET", "HEAD") else origin_page()
        return redirect(login_url(login_manager.login_view, target if is_safe_redirect(target) else None))


def _register_error_handlers(app):
    from Interfaces.ApiErrors import ApiUnavailableError

    @app.errorhandler(ApiUnavailableError)
    def handle_products_api(_error):
        # El detalle ya quedó en el log del cliente; al usuario solo un mensaje genérico.
        db.session.rollback()
        return _render_error(503)

    @app.errorhandler(CSRFError)
    def handle_csrf(_error):
        security_log("csrf_failed")
        return _render_error(400)

    @app.errorhandler(HTTPException)
    def handle_http(error):
        code = error.code or 500
        if code < 400:  # redirecciones de enrutamiento (p. ej. barra final)
            return error
        if code == 429:
            security_log("rate_limited")
        elif code == 403:
            security_log("forbidden", user=getattr(current_user, "id", "-"))
        if code not in ERROR_MESSAGES:
            code = 400 if 400 <= code < 500 else 500
        response = app.make_response(_render_error(code))
        if code == 405 and getattr(error, "valid_methods", None):
            response.headers["Allow"] = ", ".join(error.valid_methods)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        if isinstance(error, HTTPException):
            return handle_http(error)
        if app.testing and app.config.get("PROPAGATE_EXCEPTIONS") is not False:
            raise error
        db.session.rollback()
        app.logger.exception("Error no controlado")  # el detalle va al log, nunca al cliente
        return _render_error(500)
