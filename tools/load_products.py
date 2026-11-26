"""Carga masiva de productos de demostración en DynamoDB (tabla Products).

Genera productos sintéticos con el MISMO formato que escriben las Lambdas y los carga con
BatchWriteItem (boto3 `batch_writer`, de 25 en 25).

Uso (PowerShell, desde la carpeta del proyecto, con el entorno virtual activado):

    # 1) Solo generar y revisar, sin tocar AWS:
    python tools/load_products.py --seller SEL-123456 --count 17000 --dry-run

    # 2) Cargar de verdad (necesita boto3 y las credenciales del laboratorio en variables
    #    de entorno: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y AWS_SESSION_TOKEN):
    python tools/load_products.py --seller SEL-123456 --count 17000

    # 3) Borrar lo que cargó este script (los IDs son fijos y predecibles):
    python tools/load_products.py --count 17000 --undo

Los productos usan IDs PROD-90000000 en adelante, así que no se mezclan con los que crea
la aplicación (que son aleatorios). Nunca escribe contraseñas ni claves en archivos.
"""
import argparse
import random
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal

FIRST_ID = 90_000_000
SELLER_RE = re.compile(r"^SEL-[0-9]{3,8}$")

# categoría -> (prefijo de SKU, tipos de producto, rango de precio en MXN)
CATALOG = {
    "monitors": ("MON", ["Monitor", "Monitor curvo", "Monitor gamer", "Monitor portátil"], (1800, 14000)),
    "computers": ("LAP", ["Laptop", "Laptop gamer", "Computadora de escritorio", "Mini PC", "Tablet"],
                  (4500, 42000)),
    "storage": ("SSD", ["SSD externo", "Disco duro externo", "Memoria USB", "Tarjeta microSD", "SSD interno"],
                (180, 4800)),
    "networking": ("NET", ["Router WiFi", "Switch", "Repetidor WiFi", "Adaptador de red", "Punto de acceso"],
                   (250, 5200)),
    "computer-accessories": ("ACC", ["Mouse", "Teclado mecánico", "Webcam", "Base para laptop", "Hub USB-C"],
                             (120, 3800)),
    "audio": ("AUD", ["Audífonos", "Bocina Bluetooth", "Micrófono", "Barra de sonido", "Audífonos gamer"],
              (200, 7800)),
    "office": ("OFI", ["Silla ergonómica", "Escritorio", "Lámpara de escritorio", "Soporte de monitor", "Organizador"],
               (150, 9500)),
}
CATEGORY_ORDER = list(CATALOG)
BRANDS = ["Aurora", "Nexa", "Vortex", "Lumio", "Kairo", "Tecna", "Orbis", "Zenit", "Alfa", "Boreal",
          "Cuarzo", "Delta", "Eclipse", "Fenix", "Gamma", "Helix"]
FEATURES = ["con garantía de 12 meses", "con envío incluido", "en excelente estado", "con caja original",
            "listo para usar", "edición 2026", "con accesorios incluidos", "de bajo consumo"]
CONDITIONS = ["NEW"] * 6 + ["USED"] * 2 + ["REFURBISHED"] * 2


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def make_item(n, seller_ids, rng, now):
    """Un producto sintético. `n` (0, 1, 2…) fija su ID, su nombre y su SKU: no se repiten."""
    category = CATEGORY_ORDER[n % len(CATEGORY_ORDER)]
    prefix, kinds, (low, high) = CATALOG[category]
    kind = kinds[(n // len(CATEGORY_ORDER)) % len(kinds)]
    brand = BRANDS[(n * 7 + 3) % len(BRANDS)]
    code = f"{n + 1:05d}"
    name = f"{kind} {brand} {prefix}-{code}"
    feature = FEATURES[n % len(FEATURES)]
    created = now - timedelta(minutes=rng.randint(0, 60 * 24 * 90))
    rated = rng.random() < 0.35
    dist = {star: 0 for star in range(1, 6)}
    if rated:
        for _ in range(rng.randint(1, 40)):
            dist[rng.choices([1, 2, 3, 4, 5], weights=[1, 1, 3, 6, 8])[0]] += 1
    count = sum(dist.values())
    item = {
        "product_id": f"PROD-{FIRST_ID + n:08d}",
        "name": name,
        "search_name": unicodedata.normalize("NFKC", name).casefold(),
        "description": f"{kind} marca {brand}, modelo {prefix}-{code}, {feature}. Producto de demostración.",
        "category": category,
        "listed_category": category,
        "price": Decimal(f"{rng.uniform(low, high):.2f}"),
        "stock": rng.choice([0, 1, 2, 3, 5, 8, 12, 20, 35, 60, 120]),
        "seller_id": seller_ids[n % len(seller_ids)],
        "seller_sku": f"{prefix}-{code}",
        "condition": rng.choice(CONDITIONS),
        "status": "ACTIVE",
        "version": 1,
        "sales_count": rng.randint(0, 60),
        "created_at": iso(created),
        "updated_at": iso(created),
        "rating_sum": sum(star * qty for star, qty in dist.items()),
        "rating_count": count,
    }
    for star, qty in dist.items():
        item[f"rating_{star}"] = qty
    return item


def generate(count, seller_ids, seed=2026):
    rng = random.Random(seed)  # nosec B311 - datos sintéticos reproducibles; no es para seguridad
    now = datetime.now(timezone.utc)
    for n in range(count):
        yield make_item(n, seller_ids, rng, now)


def check(item):
    """Las mismas reglas que valida la Lambda (por si se cambian las listas de arriba)."""
    # Se usa ValueError y no assert: la validación no debe desaparecer si Python corre con -O.
    problems = [
        not re.fullmatch(r"PROD-[0-9]{3,8}", item["product_id"]) and f"product_id: {item['product_id']}",
        not 3 <= len(item["name"]) <= 120 and f"name: {item['name']}",
        not re.fullmatch(r"[A-Z0-9][A-Z0-9 ._-]{1,39}", item["seller_sku"]) and f"seller_sku: {item['seller_sku']}",
        not Decimal("0.01") <= item["price"] <= Decimal("9999999.99") and f"price: {item['price']}",
        not 0 <= item["stock"] <= 100000 and f"stock: {item['stock']}",
        not SELLER_RE.match(item["seller_id"]) and f"seller_id: {item['seller_id']}",
    ]
    problems = [p for p in problems if p]
    if problems:
        raise ValueError("Producto inválido: " + "; ".join(problems))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=17000, help="cuántos productos (por omisión 17000)")
    parser.add_argument("--seller", default="", help="SEL-###### de la tienda; varias separadas por coma")
    parser.add_argument("--table", default="Products", help="nombre de la tabla (por omisión Products)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true", help="solo genera y revisa; no toca AWS")
    parser.add_argument("--undo", action="store_true", help="borra los productos que cargó este script")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not 1 <= args.count <= 100_000:
        sys.exit("--count debe estar entre 1 y 100000")
    sellers = [s.strip() for s in args.seller.split(",") if s.strip()]
    if not args.undo:
        if not sellers or not all(SELLER_RE.match(s) for s in sellers):
            sys.exit("Indica --seller SEL-###### (el código de vendedor que aparece en tu perfil).")
    else:
        sellers = ["SEL-000000"]

    items = list(generate(args.count, sellers))
    for item in items:
        check(item)
    print(f"Generados {len(items)} productos (de {items[0]['product_id']} a {items[-1]['product_id']}).")
    if args.dry_run:
        for item in items[:3]:
            print(f"  {item['product_id']}  {item['seller_sku']:<10} ${item['price']:>9}  {item['name']}")
        print("Modo --dry-run: no se escribió nada en AWS.")
        return

    try:
        import boto3
    except ImportError:
        sys.exit("Falta boto3. Instálalo en tu entorno con:  pip install boto3  (solo para esta herramienta).")
    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    done = 0
    with table.batch_writer(overwrite_by_pkeys=["product_id"]) as batch:
        for item in items:
            if args.undo:
                batch.delete_item(Key={"product_id": item["product_id"]})
            else:
                batch.put_item(Item=item)
            done += 1
            if done % 1000 == 0:
                print(f"  {done} / {len(items)}")
    print(("Borrados" if args.undo else "Cargados") + f" {done} productos en la tabla {args.table}.")


if __name__ == "__main__":
    main()
