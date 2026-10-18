"""Lambda lambdaCreateOrder: POST /orders - convierte el carrito en pedidos (uno por vendedor).

Ruta: POST /orders   ·  Autorizador: mktTokenAuthorizer
Cuerpo: {"address": {recipient_name, phone, line1, line2, city, state, postal_code}}
Tablas: Marketplace (carrito), Products (existencias) y Orders (pedidos). Sin variables de
entorno. Python 3.14, rol LabRole, timeout 15 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).

Seguridad: el carrito y los precios se leen AQUÍ, de DynamoDB; del cliente solo llega la
dirección. Descontar existencias, crear los pedidos y vaciar el carrito ocurre en UNA
transacción: si alguien compró la última pieza un instante antes, no se cobra nada y no
queda nada a medias.
"""
# ---------------------------------------------------------------- lambdaCreateOrder


def _build_operations(actor, address, lines, products, now):
    by_seller = {}
    for line in lines:
        product = products[line["product_id"]]
        by_seller.setdefault(product["seller_id"], []).append((line, product))

    created = datetime.now(timezone.utc)
    estimated_from = (created + timedelta(days=DELIVERY_MIN_DAYS)).strftime("%Y-%m-%d")
    estimated_to = (created + timedelta(days=DELIVERY_MAX_DAYS)).strftime("%Y-%m-%d")
    operations, summaries = [], []

    for seller_id, group in sorted(by_seller.items()):
        order_id = new_ulid()
        pk = f"ORDER#{order_id}"
        total = sum(Decimal(p["price"]) * line["quantity"] for line, p in group)
        units = sum(line["quantity"] for line, _ in group)
        first = group[0][1]
        title = first["name"] + (f" y {len(group) - 1} más" if len(group) > 1 else "")
        header = {
            "PK": pk, "SK": "ORDER", "entity": "Order", "order_id": order_id,
            "buyer_id": actor.user_id, "seller_id": seller_id, "status": "CONFIRMED",
            "title": title[:160], "first_product_id": first["product_id"],
            "first_category": first.get("category", ""), "total": total, "units": units,
            "created_at": now, "updated_at": now,
            "estimated_from": estimated_from, "estimated_to": estimated_to,
            "GSI1PK": actor.user_key, "GSI1SK": pk,
            "GSI2PK": "STATUS#CONFIRMED", "GSI2SK": f"{now}#{order_id}",
        }
        operations.append({"Put": {"TableName": ORDERS_TABLE, "Item": header,
                                   "ConditionExpression": "attribute_not_exists(PK)"}})
        for line, product in group:
            price = Decimal(product["price"])
            operations.append({"Put": {"TableName": ORDERS_TABLE, "Item": {
                "PK": pk, "SK": f"ITEM#{product['product_id']}", "entity": "OrderItem",
                "order_id": order_id, "product_id": product["product_id"],
                "name": product["name"], "category": product.get("category", ""),
                "unit_price": price, "quantity": line["quantity"], "subtotal": price * line["quantity"],
                "seller_id": seller_id, "GSI1PK": f"SELLER#{seller_id}", "GSI1SK": pk,
            }}})
            # Descuento atómico: solo si sigue activo, hay piezas suficientes y no es del comprador.
            operations.append({"Update": {
                "TableName": PRODUCTS_TABLE,
                "Key": {"product_id": product["product_id"]},
                "UpdateExpression": ("SET stock = stock - :q, sales_count = if_not_exists(sales_count, :zero) + :q, "
                                     "#ver = if_not_exists(#ver, :one) + :one, updated_at = :now"),
                "ConditionExpression": ("attribute_exists(product_id) AND #st = :active AND stock >= :q "
                                        "AND seller_id <> :buyer"),
                "ExpressionAttributeNames": {"#st": "status", "#ver": "version"},
                "ExpressionAttributeValues": {":q": line["quantity"], ":zero": 0, ":one": 1, ":now": now,
                                              ":active": "ACTIVE", ":buyer": actor.seller_id},
            }})
        operations.append({"Put": {"TableName": ORDERS_TABLE, "Item": {
            "PK": pk, "SK": "SHIPMENT", "entity": "Shipment", "order_id": order_id, **address,
            "estimated_from": estimated_from, "estimated_to": estimated_to,
        }}})
        operations.append({"Put": {"TableName": ORDERS_TABLE, "Item": {
            "PK": pk, "SK": status_sk(now, "CONFIRMED"), "entity": "StatusChange",
            "order_id": order_id, "status": "CONFIRMED", "at": now, "by": "buyer",
        }}})
        summaries.append(order_summary(header))

    for line in lines:
        operations.append({"Delete": {"TableName": MARKETPLACE_TABLE,
                                      "Key": {"PK": actor.user_key, "SK": f"CART#{line['product_id']}"}}})
    return operations, summaries


def _comprar(event):
    actor = get_actor(event, require_user=True)
    if actor.role != "user":
        raise ApiError(403, "Solo los usuarios compran")
    data = read_body(event)
    if set(data) != {"address"}:
        raise ApiError(400, "Datos inválidos", ["Solo se acepta el campo address"])
    address = validate_address(data["address"])

    rows = query_all(
        MARKETPLACE,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :cart)",
        ExpressionAttributeValues={":pk": actor.user_key, ":cart": "CART#"},
    )
    if not rows:
        raise ApiError(400, "Tu carrito está vacío")
    lines = [{"product_id": r["product_id"], "quantity": int(r.get("quantity", 1))} for r in rows]
    products = batch_get_products(line["product_id"] for line in lines)
    problems = []
    for line in lines:
        product = products.get(line["product_id"])
        if product is None or product.get("status") != "ACTIVE":
            problems.append(f"{line['product_id']}: ya no está disponible")
        elif product.get("seller_id") == actor.seller_id:
            problems.append(f"{line['product_id']}: es tu propio producto")
        elif int(product.get("stock", 0)) < line["quantity"]:
            problems.append(f"{line['product_id']}: no hay existencias suficientes")
    if problems:
        raise ApiError(409, "Revisa tu carrito", problems)

    operations, summaries = _build_operations(actor, address, lines, products, now_iso())
    try:
        transact(operations)
    except ClientError as error:
        if cancellation_codes(error) is not None:
            raise ApiError(409, "Las existencias cambiaron mientras comprabas. Revisa tu carrito.")
        raise
    return respuesta(201, {"mensaje": "Pedido confirmado", "pedidos": summaries})


def lambda_handler(event, context):
    return run(_comprar, event, context)
