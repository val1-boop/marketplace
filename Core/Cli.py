"""Comandos de administración: `flask --app wsgi <comando>`."""
import os
from decimal import Decimal

import click
from flask import current_app

from Core.Extensions import db
from Core.ServiceRegistry import product_service
from Implementation.SharedImplementation.AccountQueries import find_user_by_email, generate_seller_id
from Interfaces.ProductServiceInterface.ProductDTO import ProductInputDTO
from Models import LoginAttempt, User, utcnow
from Security import check_password_policy, hash_password, normalize_email

# Los 8 productos con los que se trabajó en la Parte 4 del documento (categorías en inglés).
DEMO_PRODUCTS = [
    ("Laptop HP Victus", "computers", "18500.00", 7),
    ("Mouse Logitech", "computer-accessories", "500.00", 25),
    ("Monitor curvo 27 QHD", "monitors", "6499.50", 3),
    ("Teclado mecanico RGB", "computer-accessories", "1899.90", 0),
    ("Audifonos con cancelacion", "audio", "4299.00", 12),
    ("SSD externo 1TB", "storage", "2199.50", 25),
    ("Silla ergonomica", "office", "8990.00", 2),
    ("Router WiFi 6 doble banda", "networking", "1499.00", 40),
]
DEMO_DESCRIPTIONS = {
    "Laptop HP Victus": (
        "Laptop para juego y programación: Ryzen 7, 16 GB de RAM, "
        "SSD de 512 GB y pantalla de 15.6 pulgadas a 144 Hz."
    ),
    "Mouse Logitech": "Mouse inalámbrico silencioso con receptor USB, 1000 DPI y hasta 18 meses de batería.",
    "Monitor curvo 27 QHD": (
        "Monitor curvo de 27 pulgadas, resolución 2560 x 1440, "
        "165 Hz y entradas HDMI y DisplayPort."
    ),
    "Teclado mecanico RGB": "Teclado mecánico de tamaño completo con switches rojos, iluminación RGB y reposamuñecas.",
    "Audifonos con cancelacion": (
        "Audífonos inalámbricos con cancelación activa de ruido, "
        "30 horas de batería y carga rápida."
    ),
    "SSD externo 1TB": "Disco de estado sólido portátil de 1 TB con USB-C, hasta 1050 MB/s y carcasa resistente.",
    "Silla ergonomica": "Silla de oficina con soporte lumbar ajustable, respaldo de malla y descansabrazos 3D.",
    "Router WiFi 6 doble banda": "Router WiFi 6 AX3000 de doble banda con 4 antenas y control parental.",
}
# SKU público de cada producto demo (el vendedor lo define; no es el product_id interno).
DEMO_SKUS = {
    "Laptop HP Victus": "LAP-HPV-001",
    "Mouse Logitech": "MOU-LOG-002",
    "Monitor curvo 27 QHD": "MON-27Q-003",
    "Teclado mecanico RGB": "TEC-RGB-004",
    "Audifonos con cancelacion": "AUD-ANC-005",
    "SSD externo 1TB": "SSD-1TB-006",
    "Silla ergonomica": "SIL-ERG-007",
    "Router WiFi 6 doble banda": "ROU-WIFI6-008",
}


def _create_user(email, first, last, password, role):
    errors = check_password_policy(password, email)
    if errors:
        raise click.ClickException(f"Contraseña de {email} no cumple la política: {' '.join(errors)}")
    existing = find_user_by_email(email)
    if existing is not None:
        click.echo(f"Ya existe: {email}")
        return existing
    now = utcnow()
    user = User(
        email=email, email_normalized=normalize_email(email), first_name=first, last_name=last,
        password_hash=hash_password(password), role=role, status="active",
        seller_id=generate_seller_id() if role == "user" else None,
        terms_version=current_app.config["TERMS_VERSION"],
        privacy_version=current_app.config["PRIVACY_VERSION"],
        terms_accepted_at=now, password_changed_at=now,
    )
    db.session.add(user)
    db.session.flush()
    click.echo(f"Creado {role}: {email}")
    return user


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas que falten (en local, SQLite). En RDS ya existen por la Parte 5."""
        db.create_all()
        click.echo("Tablas creadas (las que no existían).")

    @app.cli.command("check-aws")
    def check_aws():
        """Comprueba la conexión con RDS MySQL, RDS PostgreSQL y el API de productos."""
        db.session.execute(db.select(db.func.count()).select_from(User))
        click.echo("MySQL (users): OK")
        db.session.execute(db.select(db.func.count()).select_from(LoginAttempt))
        click.echo("PostgreSQL (login_attempts): OK")
        api = product_service().api
        products = api.list_products()
        click.echo(f"API de productos: OK ({len(products)} productos en DynamoDB)")
        # Rutas de la tienda (entrega 2) con un usuario ficticio: solo leen, no escriben nada.
        probe = ("user", "SEL-000000", "00000000-0000-4000-8000-000000000000")
        checks = [("GET /cart", "/cart", probe), ("GET /favorites", "/favorites", probe),
                  ("GET /orders", "/orders", probe), ("GET /sales", "/sales", probe)]
        if products:
            checks.append(("GET /products/{id}/reviews", f"/products/{products[0].product_id}/reviews", None))
        for label, path, actor in checks:
            try:
                api.request("GET", path, actor=actor)
            except Exception as error:  # se informa la ruta que falla, sin detalles internos
                click.echo(f"{label}: FALLA ({type(error).__name__}). Revisa la ruta, su integración y el autorizador.")
            else:
                click.echo(f"{label}: OK")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Crea un admin, un vendedor y publica los 8 productos de demostración vía API."""
        if current_app.config["APP_ENV"] == "production":
            raise click.ClickException("seed-demo no se permite en producción.")
        required = ["SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD", "SEED_USER_EMAIL", "SEED_USER_PASSWORD"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise click.ClickException(f"Faltan variables en .env: {', '.join(missing)}")
        _create_user(os.environ["SEED_ADMIN_EMAIL"], "Ada", "Admin", os.environ["SEED_ADMIN_PASSWORD"], "admin")
        seller = _create_user(os.environ["SEED_USER_EMAIL"], "Luis", "Vendedor",
                              os.environ["SEED_USER_PASSWORD"], "user")
        db.session.commit()
        if not seller.seller_id:
            raise click.ClickException("El usuario vendedor no tiene seller_id (¿es administrador?).")
        products = product_service()
        if products.list_seller_products(seller.seller_id):
            click.echo("El vendedor ya tiene productos; no se duplican.")
            return
        for name, category, price, stock in DEMO_PRODUCTS:
            product = products.create_product(seller.seller_id, ProductInputDTO(
                name=name, category=category, price=Decimal(price), stock=stock, condition="NEW",
                description=DEMO_DESCRIPTIONS[name], seller_sku=DEMO_SKUS.get(name, ""),
            ))
            click.echo(f"  {product.product_id}  {name}")
        click.echo("Datos de demostración listos.")

    @app.cli.command("seed-descriptions")
    def seed_descriptions():
        """Agrega la descripción a los productos de demostración creados antes de la entrega 2."""
        email = os.environ.get("SEED_USER_EMAIL")
        seller = find_user_by_email(email) if email else None
        if seller is None or not seller.seller_id:
            raise click.ClickException("No existe el vendedor de demostración (SEED_USER_EMAIL).")
        products = product_service()
        updated = 0
        for product in products.list_seller_products(seller.seller_id):
            text = DEMO_DESCRIPTIONS.get(product.name)
            if not text or product.description:
                continue
            products.update_product(product.product_id, seller.seller_id, ProductInputDTO(
                name=product.name, category=product.category, price=product.price, stock=product.stock,
                condition=product.condition, description=text, seller_sku=product.seller_sku,
            ), product.version)
            updated += 1
            click.echo(f"  {product.product_id}  {product.name}")
        click.echo(f"Descripciones agregadas: {updated}.")

    @app.cli.command("seed-skus")
    def seed_skus():
        """Asigna el SKU público a los productos de demostración que aún no lo tienen."""
        email = os.environ.get("SEED_USER_EMAIL")
        seller = find_user_by_email(email) if email else None
        if seller is None or not seller.seller_id:
            raise click.ClickException("No existe el vendedor de demostración (SEED_USER_EMAIL).")
        products = product_service()
        updated = 0
        for product in products.list_seller_products(seller.seller_id):
            sku = DEMO_SKUS.get(product.name)
            if not sku or product.seller_sku:
                continue
            products.update_product(product.product_id, seller.seller_id, ProductInputDTO(
                name=product.name, category=product.category, price=product.price, stock=product.stock,
                condition=product.condition, description=product.description, seller_sku=sku,
            ), product.version)
            updated += 1
            click.echo(f"  {product.product_id}  {product.name}  {sku}")
        click.echo(f"SKU agregados: {updated}.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--first-name", prompt=True)
    @click.option("--last-name", prompt=True)
    @click.password_option()
    def create_admin(email, first_name, last_name, password):
        """Crea un administrador pidiendo la contraseña de forma oculta."""
        _create_user(email, first_name, last_name, password, "admin")
        db.session.commit()
