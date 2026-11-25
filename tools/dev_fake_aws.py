"""Arranque LOCAL de la app SIN AWS, para desarrollar y probar las pantallas.

Qué hace:
- Usa SQLite en la carpeta `instance/` en lugar de RDS MySQL y PostgreSQL.
- Usa el API Gateway y el DynamoDB SIMULADOS de las pruebas (`tests/aws_fakes.py`), que
  ejecutan las Lambdas reales de `aws/lambdas/` contra tablas en memoria.
- Crea tres cuentas de prueba y los 8 productos de demostración.

Importante:
- Es solo para DESARROLLO: no se conecta a AWS, ignora el `.env` real y borra sus datos
  cada vez que se arranca (los productos, pedidos y carritos viven en memoria).
- Las contraseñas se generan al azar en cada arranque y se muestran en la terminal.
- Uso:  python tools/dev_fake_aws.py   ->  http://localhost:5000
"""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACCOUNTS = {
    "admin": ("admin@marketplace.mx", "Ada", "Admin"),
    "vendedor": ("vendedor@marketplace.mx", "Vera", "Vendedora"),
    "comprador": ("comprador@marketplace.mx", "Carlos", "Comprador"),
}


def _password():
    # Cumple la política de la app: 12+ caracteres y 3 tipos de carácter.
    return f"Dev-{secrets.token_urlsafe(9)}-2026!"


def build_app():
    """Crea la app con AWS simulado y datos de prueba. Devuelve (app, contraseñas)."""
    instance = ROOT / "instance"
    instance.mkdir(exist_ok=True)
    main_db, security_db = instance / "dev_fake.db", instance / "dev_fake_security.db"
    for path in (main_db, security_db):
        path.unlink(missing_ok=True)

    passwords = {key: _password() for key in ACCOUNTS}
    token = secrets.token_urlsafe(48)
    url = "https://fake.execute-api.us-east-1.amazonaws.com"
    # Se definen ANTES de crear la app: load_dotenv() no sobrescribe variables ya definidas,
    # así que un .env real (con claves de AWS) nunca se usa aquí.
    os.environ.update({
        "APP_ENV": "development",
        "SECRET_KEY": secrets.token_urlsafe(64),
        "DATABASE_URL": f"sqlite:///{main_db.as_posix()}",
        "SECURITY_DATABASE_URL": f"sqlite:///{security_db.as_posix()}",
        "PRODUCTS_API_URL": url,
        "PRODUCTS_API_TOKEN": token,
        "PRODUCT_LIST_CACHE_SECONDS": "0",  # los cambios se ven al instante
        "SEED_ADMIN_EMAIL": ACCOUNTS["admin"][0],
        "SEED_ADMIN_PASSWORD": passwords["admin"],
        "SEED_USER_EMAIL": ACCOUNTS["vendedor"][0],
        "SEED_USER_PASSWORD": passwords["vendedor"],
    })
    # Estos valores se pueden cambiar desde fuera (por ejemplo, en una demostración pública
    # detrás de HTTPS: SESSION_COOKIE_SECURE=true, ALLOWED_HOSTS=tu-dominio, TRUSTED_PROXY_COUNT=1).
    os.environ.setdefault("SESSION_COOKIE_SECURE", "false")   # local: se prueba por http://localhost
    os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")
    os.environ.setdefault("TRUSTED_PROXY_COUNT", "0")

    from Core import create_app
    from Core.Cli import _create_user
    from Core.Extensions import db
    from Implementation.ProductServiceImplementation.ProductsApiClient import ProductsAPI
    from tests.aws_fakes import FakeApiGateway, FakeTable

    app = create_app("development")
    gateway = FakeApiGateway(url, FakeTable(), token)
    app.extensions["products_api"] = ProductsAPI(url, token, session=gateway)
    app.extensions["fake_gateway"] = gateway

    with app.app_context():
        db.create_all()
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    if result.exit_code != 0:
        raise SystemExit(f"No se pudieron crear los datos de prueba:\n{result.output}")
    with app.app_context():
        email, first, last = ACCOUNTS["comprador"]
        _create_user(email, first, last, passwords["comprador"], "user")
        db.session.commit()
    return app, passwords


def main():
    app, passwords = build_app()
    port = int(os.environ.get("PORT", "5000"))
    print("\n=== Marketplace en modo local SIN AWS ===")
    print(f"Abre http://localhost:{port}   (usa 'localhost', no '127.0.0.1')")
    print("Cuentas de prueba (las contraseñas cambian en cada arranque):")
    for key, (email, _first, _last) in ACCOUNTS.items():
        print(f"  {key:<10} {email:<28} {passwords[key]}")
    print("Para detener el servidor: Ctrl+C\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
