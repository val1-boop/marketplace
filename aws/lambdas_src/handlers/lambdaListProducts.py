"""Lambda lambdaListProducts: GET /products - lista todos los productos o los de un vendedor.

Ruta: GET /products y GET /products?seller_id=SEL-######   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaListProducts
# GET /products                 -> todos los productos (scan paginado)
# GET /products?seller_id=SEL-x -> productos de un vendedor (índice bySeller)
# Paginación opcional: ?limit=1..500 devuelve esa cantidad y un "next_cursor" para pedir la
# página siguiente con ?cursor=<next_cursor>. Sin "limit" se conserva el comportamiento
# anterior (hasta 1000 productos), así las pantallas viejas siguen funcionando.
MAX_ITEMS = 1000
PAGE_MAX = 500
CURSOR_MAX = 400


def _encode_cursor(key):
    raw = json.dumps(key, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(text, by_seller):
    """El cursor lo arma la propia Lambda, pero viaja por el servidor Flask: se valida
    como cualquier entrada (largo, formato y claves permitidas)."""
    try:
        if not isinstance(text, str) or not 1 <= len(text) <= CURSOR_MAX:
            raise ValueError
        key = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8"))
        allowed = {"product_id", "seller_id"} if by_seller else {"product_id"}
        if not isinstance(key, dict) or set(key) != allowed:
            raise ValueError
        if not isinstance(key["product_id"], str) or not PRODUCT_ID_RE.match(key["product_id"]):
            raise ValueError
        if by_seller and not (isinstance(key["seller_id"], str) and SELLER_ID_RE.match(key["seller_id"])):
            raise ValueError
        return key
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "cursor no es válido")


def _listar(event):
    params = event.get("queryStringParameters") or {}
    seller_id = params.get("seller_id")
    limit = None
    if params.get("limit") is not None:
        limit = parse_int(params.get("limit"), 1, PAGE_MAX)
        if limit is None:
            raise ApiError(400, f"limit debe ser un entero de 1 a {PAGE_MAX}")
    kwargs = {}
    if seller_id is not None:
        if not SELLER_ID_RE.match(seller_id):
            raise ApiError(400, "seller_id no es válido")
        operation = TABLE.query
        kwargs = {
            "IndexName": "bySeller",
            "KeyConditionExpression": "seller_id = :s",
            "ExpressionAttributeValues": {":s": seller_id},
        }
    else:
        operation = TABLE.scan
    if params.get("cursor") is not None:
        kwargs["ExclusiveStartKey"] = _decode_cursor(params.get("cursor"), seller_id is not None)
    if limit is not None:
        # Una sola página: el servidor pide la siguiente con el next_cursor.
        page = operation(Limit=limit, **kwargs)
        last_key = page.get("LastEvaluatedKey")
        return respuesta(200, {"productos": [public(item) for item in page.get("Items", [])],
                               "next_cursor": _encode_cursor(last_key) if last_key else None})
    items = []
    while True:
        page = operation(**kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key or len(items) >= MAX_ITEMS:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return respuesta(200, {"productos": [public(item) for item in items[:MAX_ITEMS]], "next_cursor": None})


def lambda_handler(event, context):
    return run(_listar, event, context)
