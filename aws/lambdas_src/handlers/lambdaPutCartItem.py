"""Lambda lambdaPutCartItem: PUT /cart/{product_id} - agrega un producto al carrito o cambia su cantidad.

Ruta: PUT /cart/{product_id}   ·  Autorizador: mktTokenAuthorizer
Cuerpo: {"quantity": 1..10, "mode": "add" | "set"}
Tablas: Marketplace (USER#<id> / CART#<producto>, caduca a los 30 días por TTL) y Products.
Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaPutCartItem


def _guardar(event):
    actor = get_actor(event, require_user=True)
    if actor.role != "user":
        raise ApiError(403, "Solo los usuarios compran")
    product_id = get_product_id(event)
    data = read_body(event)
    if set(data) - {"quantity", "mode"}:
        raise ApiError(400, "Campos no permitidos")
    quantity = parse_int(data.get("quantity", 1), 1, CART_MAX_QTY)
    mode = data.get("mode", "add")
    if quantity is None or mode not in ("add", "set"):
        raise ApiError(400, "Datos inválidos", [f"quantity debe estar entre 1 y {CART_MAX_QTY}"])

    product = TABLE.get_item(Key={"product_id": product_id}).get("Item")
    if product is None or product.get("status") != "ACTIVE":
        raise ApiError(404, "Producto no encontrado")
    if product.get("seller_id") == actor.seller_id:
        raise ApiError(409, "No puedes comprar tus propios productos")

    key = {"PK": actor.user_key, "SK": f"CART#{product_id}"}
    current = MARKETPLACE.get_item(Key=key).get("Item")
    if current is None:
        lines = MARKETPLACE.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :cart)",
            ExpressionAttributeValues={":pk": actor.user_key, ":cart": "CART#"},
            Select="COUNT",
        ).get("Count", 0)
        if lines >= CART_MAX_LINES:
            raise ApiError(409, f"El carrito admite máximo {CART_MAX_LINES} productos distintos")
    if mode == "add" and current is not None:
        quantity = min(int(current.get("quantity", 0)) + quantity, CART_MAX_QTY)
    if int(product.get("stock", 0)) < quantity:
        raise ApiError(409, "No hay existencias suficientes")

    now = now_iso()
    MARKETPLACE.put_item(Item={
        **key,
        "entity": "CartItem",
        "product_id": product_id,
        "quantity": quantity,
        "quoted_price": Decimal(product["price"]),  # solo de referencia; al pagar se usa el actual
        "added_at": current.get("added_at", now) if current else now,
        "updated_at": now,
        "expires_at": int(time.time()) + CART_TTL_DAYS * 86400,
    })
    return respuesta(200, {"mensaje": "Carrito actualizado", "product_id": product_id, "quantity": quantity})


def lambda_handler(event, context):
    return run(_guardar, event, context)
