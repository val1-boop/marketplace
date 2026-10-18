"""Lambda lambdaListFavorites: GET /favorites - los productos favoritos de quien llama.

Ruta: GET /favorites   ·  Autorizador: mktTokenAuthorizer
Tablas: Community (USER#<id> / FAV#<producto>) y Products. Sin variables de entorno.
Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
import base64
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import boto3
from botocore.exceptions import ClientError

# ============================================================================
# Ayudantes comunes (iguales en todas las Lambdas; se generan desde
# aws/lambdas_src/common.py con tools/build_lambdas.py: NO los edites aquí).
# ============================================================================

# Tablas de la Parte 5. Si en tu laboratorio se llaman igual, NO necesitas variables de
# entorno: los valores por omisión ya son los nombres correctos.
DYNAMO = boto3.resource("dynamodb")
PRODUCTS_TABLE = os.environ.get("TABLE_NAME", "Products")
ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "Orders")
MARKETPLACE_TABLE = os.environ.get("MARKETPLACE_TABLE", "Marketplace")
COMMUNITY_TABLE = os.environ.get("COMMUNITY_TABLE", "Community")
TABLE = DYNAMO.Table(PRODUCTS_TABLE)          # Products (product_id)
ORDERS = DYNAMO.Table(ORDERS_TABLE)          # Orders (PK, SK, GSI1, GSI2)
MARKETPLACE = DYNAMO.Table(MARKETPLACE_TABLE)  # Marketplace (PK, SK): carrito
COMMUNITY = DYNAMO.Table(COMMUNITY_TABLE)    # Community (PK, SK, GSI1): reseñas, favoritos

PRODUCT_ID_RE = re.compile(r"^PROD-[0-9]{3,8}\Z")
SELLER_ID_RE = re.compile(r"^SEL-[0-9]{3,8}\Z")
USER_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
ORDER_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}\Z")
DISPLAY_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '.\-][^\W\d_]+)*\.?\Z")
CATEGORIES = {"monitors", "computers", "storage", "networking", "computer-accessories", "audio", "office"}
CONDITIONS = {"NEW", "USED", "REFURBISHED"}
PRODUCT_FIELDS = {"name", "description", "category", "price", "stock", "condition", "seller_sku"}
# SKU público que escribe el vendedor (opcional): letras, números y . - _ (y espacios), 2 a 40.
SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9 ._-]{1,39}\Z")
MX_STATES = {
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas",
    "Chihuahua", "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México",
    "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán", "Morelos", "Nayarit",
    "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
}
MAX_BODY = 8192
CART_MAX_LINES = 10
CART_MAX_QTY = 10
CART_TTL_DAYS = 30
FAVORITES_MAX = 100
# "name", "status", "condition" y "version" pueden chocar con palabras reservadas de DynamoDB.
NAMES = {"#n": "name", "#st": "status", "#cond": "condition", "#ver": "version"}


def names_for(*expressions):
    """Solo los #nombres que de verdad aparecen en las expresiones: DynamoDB rechaza
    (ValidationException) un ExpressionAttributeNames con nombres sin usar."""
    text = " ".join(e for e in expressions if e)
    return {k: v for k, v in NAMES.items() if re.search(re.escape(k) + r"(?![A-Za-z0-9_])", text)}


class ApiError(Exception):
    def __init__(self, status, message, errors=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.errors = errors or []


class Actor:
    """Quién hace la operación. Solo Flask puede llamar al API (lo garantiza el
    autorizador), así que estas cabeceras vienen del servidor, nunca del navegador."""

    def __init__(self, role, seller_id, user_id):
        self.role = role
        self.seller_id = seller_id
        self.user_id = user_id

    @property
    def user_key(self):
        return f"USER#{self.user_id}"


def respuesta(status, body):
    """Respuesta en el formato que espera API Gateway (payload 2.0). Sin CORS:
    el navegador nunca llama a este API, solo el servidor Flask."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid():
    """ULID: 26 caracteres ordenables por tiempo (48 bits de milisegundos + 80 al azar)."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(secrets.token_bytes(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def _headers(event):
    return {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}


def get_actor(event, require_user=False):
    headers = _headers(event)
    role = headers.get("x-mkt-actor-role", "")
    seller = headers.get("x-mkt-actor-seller", "")
    user = headers.get("x-mkt-actor-user", "")
    if role not in ("user", "admin"):
        raise ApiError(403, "Actor no válido")
    if role == "user" and not SELLER_ID_RE.match(seller):
        raise ApiError(403, "Actor no válido")
    if role == "admin":
        seller = ""
    if require_user and not USER_ID_RE.match(user):
        raise ApiError(403, "Actor no válido")
    if user and not USER_ID_RE.match(user):
        raise ApiError(403, "Actor no válido")
    return Actor(role, seller, user)


def get_optional_actor(event):
    """Actor si viene completo (para personalizar una respuesta pública); si no, None."""
    try:
        return get_actor(event, require_user=True)
    except ApiError:
        return None


def get_product_id(event):
    product_id = (event.get("pathParameters") or {}).get("product_id", "")
    if not isinstance(product_id, str) or not PRODUCT_ID_RE.match(product_id):
        raise ApiError(404, "Producto no encontrado")
    return product_id


def get_order_id(event):
    order_id = (event.get("pathParameters") or {}).get("order_id", "")
    if not isinstance(order_id, str) or not ORDER_ID_RE.match(order_id):
        raise ApiError(404, "Pedido no encontrado")
    return order_id


def read_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Cuerpo inválido")
    if len(raw) > MAX_BODY:
        raise ApiError(413, "Cuerpo demasiado grande")
    if not raw:
        raise ApiError(400, "El cuerpo de la petición está vacío")
    try:
        data = json.loads(raw, parse_float=Decimal)
    except ValueError:
        raise ApiError(400, "JSON inválido")
    if not isinstance(data, dict):
        raise ApiError(400, "Se esperaba un objeto JSON")
    return data


def parse_price(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        price = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price.as_tuple().exponent < -2:
        return None
    if price < Decimal("0.01") or price > Decimal("9999999.99"):
        return None
    return price.quantize(Decimal("0.01"))


def parse_int(value, minimum, maximum):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            return None
        value = int(value)
    elif isinstance(value, str):
        value = value.strip()
        if not value.isascii() or not value.isdigit() or len(value) > 9:
            return None
        value = int(value)
    elif not isinstance(value, int):
        return None
    return value if minimum <= value <= maximum else None


def clean_text(value, minimum, maximum, allow_newlines=False):
    """Texto normalizado (NFC) o None si no cumple longitud o trae caracteres de control."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).strip()
    if allow_newlines:
        text = text.replace("\r\n", "\n")
    if not minimum <= len(text) <= maximum:
        return None
    allowed = {"\n"} if allow_newlines else set()
    if any(unicodedata.category(c).startswith("C") and c not in allowed for c in text):
        return None
    return text


def validate_product(data, allowed_extra=()):
    """Lista blanca de campos y validación (la segunda capa, después de Flask)."""
    errors = []
    unknown = set(data) - PRODUCT_FIELDS - set(allowed_extra)
    if unknown:
        errors.append("Campos no permitidos: " + ", ".join(sorted(str(k)[:30] for k in unknown)))
    name = clean_text(data.get("name"), 3, 120)
    if name is None:
        errors.append("name debe tener entre 3 y 120 caracteres, sin caracteres de control")
    description = data.get("description", "")
    description = clean_text(description, 0, 2000, allow_newlines=True) if description != "" else ""
    if description is None:
        errors.append("description admite hasta 2000 caracteres, sin caracteres de control")
    category = data.get("category")
    if category not in CATEGORIES:
        errors.append("category no es válida")
    condition = data.get("condition", "NEW")
    if condition not in CONDITIONS:
        errors.append("condition no es válida")
    price = parse_price(data.get("price"))
    if price is None:
        errors.append("price debe estar entre 0.01 y 9999999.99 con máximo 2 decimales")
    stock = parse_int(data.get("stock"), 0, 100000)
    if stock is None:
        errors.append("stock debe ser un entero entre 0 y 100000")
    # SKU público del vendedor: opcional. Si viene vacío se guarda como "".
    raw_sku = data.get("seller_sku", "")
    if raw_sku is None or raw_sku == "":
        seller_sku = ""
    elif isinstance(raw_sku, str) and SKU_RE.match(unicodedata.normalize("NFKC", raw_sku).strip().upper()):
        seller_sku = unicodedata.normalize("NFKC", raw_sku).strip().upper()
    else:
        seller_sku = None
        errors.append("seller_sku admite de 2 a 40 caracteres: letras, números, espacio y . - _")
    if errors:
        raise ApiError(400, "Datos inválidos", errors)
    return {
        "name": name,
        "search_name": unicodedata.normalize("NFKC", name).casefold(),
        "description": description,
        "category": category,
        "condition": condition,
        "price": price,
        "stock": stock,
        "seller_sku": seller_sku,
    }


def money(value):
    return f"{Decimal(value or 0):.2f}"


def public(item):
    """Producto: solo se devuelven estos campos (lista blanca de salida)."""
    count = int(item.get("rating_count", 0) or 0)
    total = Decimal(item.get("rating_sum", 0) or 0)
    return {
        "product_id": item["product_id"],
        "name": item.get("name", ""),
        "search_name": item.get("search_name", ""),
        "description": item.get("description", ""),
        "category": item.get("category", ""),
        "price": money(item.get("price", 0)),
        "stock": int(item.get("stock", 0)),
        "seller_id": item.get("seller_id", ""),
        "seller_sku": item.get("seller_sku", ""),
        "condition": item.get("condition", "NEW"),
        "status": item.get("status", "ACTIVE"),
        "blocked_reason": item.get("blocked_reason"),
        "version": int(item.get("version", 1)),
        "rating_count": count,
        "rating_avg": f"{(total / count):.1f}" if count else "0.0",
        "rating_dist": {str(n): int(item.get(f"rating_{n}", 0) or 0) for n in range(1, 6)},
        "sales_count": int(item.get("sales_count", 0) or 0),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def is_conditional_failure(error):
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def cancellation_codes(error):
    """Códigos de cada operación de una transacción cancelada (None = no falló)."""
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return None
    return [r.get("Code") for r in error.response.get("CancellationReasons", [])]


def transact(operations):
    """TransactWriteItems: TODO se aplica o NADA (descontar existencias, crear el pedido
    y vaciar el carrito en un solo paso). El cliente del recurso acepta tipos de Python."""
    DYNAMO.meta.client.transact_write_items(TransactItems=operations)


def batch_get_products(product_ids):
    """Productos por ID (BatchGetItem). Devuelve {product_id: item}."""
    ids = sorted(set(product_ids))
    found = {}
    for start in range(0, len(ids), 100):
        keys = [{"product_id": pid} for pid in ids[start:start + 100]]
        result = DYNAMO.batch_get_item(RequestItems={PRODUCTS_TABLE: {"Keys": keys}})
        for item in result.get("Responses", {}).get(PRODUCTS_TABLE, []):
            found[item["product_id"]] = item
    return found


def query_all(table, **kwargs):
    """Query con paginación (LastEvaluatedKey) hasta `Limit` total si se indica."""
    limit = kwargs.pop("Limit", None)
    items = []
    while True:
        params = dict(kwargs)
        if limit:
            params["Limit"] = limit - len(items)
        result = table.query(**params)
        items.extend(result.get("Items", []))
        if "LastEvaluatedKey" not in result or (limit and len(items) >= limit):
            return items
        kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]


def run(handler, event, context):
    """Errores controlados con su código; cualquier otro, 500 sin detalles internos."""
    try:
        return handler(event)
    except ApiError as error:
        body = {"mensaje": error.message}
        if error.errors:
            body["errores"] = error.errors
        return respuesta(error.status, body)
    except Exception as error:  # el detalle queda en CloudWatch, no en la respuesta
        print("ERROR", type(error).__name__, repr(error)[:500])
        return respuesta(500, {"mensaje": "Error interno",
                               "request_id": getattr(context, "aws_request_id", "-")})


# ---------------------------------------------------------------- pedidos (tabla Orders)
# ORDER#<id> / ORDER      encabezado (GSI1: USER#<comprador>, GSI2: STATUS#<estado>)
# ORDER#<id> / ITEM#<p>   renglón     (GSI1: SELLER#<vendedor>, para "Mis ventas")
# ORDER#<id> / SHIPMENT   envío: copia de la dirección y fechas
# ORDER#<id> / STATUS#<t> historial de estados
ORDER_STATUSES = ("CONFIRMED", "PREPARING", "SHIPPED", "DELIVERED", "CANCELLED")


def status_sk(now, status):
    """Clave del historial: fecha + número de paso, para que dos cambios en el mismo
    milisegundo queden en su orden lógico."""
    return f"STATUS#{now}#{ORDER_STATUSES.index(status) + 1}{status}"
DELIVERY_MIN_DAYS = 3
DELIVERY_MAX_DAYS = 7
ADDRESS_FIELDS = {"recipient_name", "phone", "line1", "line2", "city", "state", "postal_code"}


def validate_address(data):
    """Dirección de envío (copia que Flask toma de RDS addresses). Lista blanca y formato."""
    if not isinstance(data, dict):
        raise ApiError(400, "Datos inválidos", ["address debe ser un objeto"])
    errors = []
    unknown = set(data) - ADDRESS_FIELDS
    if unknown:
        errors.append("Campos no permitidos en address: " + ", ".join(sorted(str(k)[:30] for k in unknown)))
    clean = {
        "recipient_name": clean_text(data.get("recipient_name"), 2, 120),
        "phone": data.get("phone") if isinstance(data.get("phone"), str) and re.fullmatch(r"[0-9]{10}", data.get("phone")) else None,
        "line1": clean_text(data.get("line1"), 3, 120),
        "line2": clean_text(data.get("line2", ""), 0, 120) if data.get("line2") else "",
        "city": clean_text(data.get("city"), 2, 80),
        "state": data.get("state") if data.get("state") in MX_STATES else None,
        "postal_code": data.get("postal_code") if isinstance(data.get("postal_code"), str) and re.fullmatch(r"[0-9]{5}", data.get("postal_code")) else None,
    }
    for field, value in clean.items():
        if value is None:
            errors.append(f"{field} no es válido")
    if errors:
        raise ApiError(400, "Datos inválidos", errors)
    clean["country"] = "MX"
    return clean


def order_summary(header):
    """Encabezado de pedido para listas (lista blanca de salida)."""
    return {
        "order_id": header["order_id"],
        "status": header.get("status", ""),
        "title": header.get("title", ""),
        "first_product_id": header.get("first_product_id", ""),
        "first_category": header.get("first_category", ""),
        "total": money(header.get("total", 0)),
        "units": int(header.get("units", 0)),
        "seller_id": header.get("seller_id", ""),
        "created_at": header.get("created_at", ""),
        "updated_at": header.get("updated_at", ""),
        "estimated_from": header.get("estimated_from", ""),
        "estimated_to": header.get("estimated_to", ""),
    }


def load_order(order_id):
    """Todo el pedido (encabezado, renglones, envío e historial) en UNA consulta."""
    rows = query_all(ORDERS, KeyConditionExpression="PK = :pk",
                     ExpressionAttributeValues={":pk": f"ORDER#{order_id}"})
    header = next((r for r in rows if r["SK"] == "ORDER"), None)
    if header is None:
        return None
    return {
        "header": header,
        "items": [r for r in rows if r["SK"].startswith("ITEM#")],
        "shipment": next((r for r in rows if r["SK"] == "SHIPMENT"), {}),
        "history": sorted((r for r in rows if r["SK"].startswith("STATUS#")), key=lambda r: r["SK"]),
    }


def can_see_order(order, actor):
    header = order["header"]
    return (actor.role == "admin"
            or (actor.user_id and header.get("buyer_id") == actor.user_id)
            or (actor.seller_id and header.get("seller_id") == actor.seller_id))


def order_detail(order, actor):
    header, shipment = order["header"], order["shipment"]
    detail = order_summary(header)
    detail.update({
        "viewer": ("buyer" if header.get("buyer_id") == actor.user_id
                   else "seller" if header.get("seller_id") == actor.seller_id else "admin"),
        "items": [{
            "product_id": i["product_id"], "name": i.get("name", ""), "category": i.get("category", ""),
            "unit_price": money(i.get("unit_price", 0)), "quantity": int(i.get("quantity", 0)),
            "subtotal": money(i.get("subtotal", 0)),
        } for i in order["items"]],
        "shipment": {k: shipment.get(k, "") for k in
                     ("recipient_name", "phone", "line1", "line2", "city", "state", "postal_code",
                      "country", "shipped_at", "delivered_at")},
        "history": [{"status": h.get("status", ""), "at": h.get("at", ""), "by": h.get("by", "")}
                    for h in order["history"]],
    })
    return detail


# ---------------------------------------------------------------- lambdaListFavorites


def _listar(event):
    actor = get_actor(event, require_user=True)
    rows = query_all(
        COMMUNITY,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :fav)",
        ExpressionAttributeValues={":pk": actor.user_key, ":fav": "FAV#"},
        Limit=FAVORITES_MAX,
    )
    rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    products = batch_get_products(row["product_id"] for row in rows)
    favorites = []
    for row in rows:
        item = products.get(row["product_id"])
        # Un producto borrado, bloqueado o retirado no se muestra (solo su ID, para poder quitarlo).
        visible = item is not None and item.get("status") == "ACTIVE"
        favorites.append({
            "product_id": row["product_id"],
            "added_at": row.get("created_at", ""),
            "producto": public(item) if visible else None,
        })
    return respuesta(200, {"favoritos": favorites})


def lambda_handler(event, context):
    return run(_listar, event, context)
