"""Rutas del API para la tienda. Cada ID se valida con lista blanca ANTES de armar la ruta,
así un valor como `../orders` nunca llega a API Gateway (sin path traversal)."""
import re
from urllib.parse import quote

from Interfaces.ApiErrors import NotFoundError
from Security import PRODUCT_ID_RE

ORDER_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}\Z")  # ULID, igual que en la Lambda


def product_path(prefix, product_id, suffix=""):
    if not isinstance(product_id, str) or not PRODUCT_ID_RE.match(product_id):
        raise NotFoundError("ID de producto inválido")
    return f"{prefix}/{quote(product_id, safe='')}{suffix}"


def order_path(order_id):
    if not isinstance(order_id, str) or not ORDER_ID_RE.match(order_id):
        raise NotFoundError("ID de pedido inválido")
    return "/orders/" + quote(order_id, safe="")
