"""Lambda lambdaUpdateOrderStatus: PUT /orders/{order_id} - avanza o cancela un pedido.

Ruta: PUT /orders/{order_id}   ·  Autorizador: mktTokenAuthorizer
Cuerpo: {"action": "prepare" | "ship" | "deliver" | "cancel", "reason": "opcional al cancelar"}
Tablas: Orders, Products (devolver existencias al cancelar) y Community (registro de compra
entregada, que habilita la reseña). Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).

Estados (como Mercado Libre):  CONFIRMED → PREPARING → SHIPPED → DELIVERED,  o CANCELLED.
- El VENDEDOR prepara y envía.  - El COMPRADOR confirma que lo recibió.
- Cancelar: el comprador mientras está CONFIRMED; el vendedor hasta PREPARING; un admin
  hasta SHIPPED. Al cancelar, las existencias regresan al producto.
Cada cambio es condicional al estado leído: dos clics a la vez no saltan estados.
"""
# ---------------------------------------------------------------- lambdaUpdateOrderStatus
TRANSITIONS = {
    "prepare": {"to": "PREPARING", "from": {"seller": {"CONFIRMED"}}},
    "ship": {"to": "SHIPPED", "from": {"seller": {"PREPARING"}}},
    "deliver": {"to": "DELIVERED", "from": {"buyer": {"SHIPPED"}}},
    "cancel": {"to": "CANCELLED", "from": {"buyer": {"CONFIRMED"},
                                           "seller": {"CONFIRMED", "PREPARING"},
                                           "admin": {"CONFIRMED", "PREPARING", "SHIPPED"}}},
}


def _role_in_order(header, actor):
    if actor.role == "admin":
        return "admin"
    if actor.user_id and header.get("buyer_id") == actor.user_id:
        return "buyer"
    if actor.seller_id and header.get("seller_id") == actor.seller_id:
        return "seller"
    return None


def _cambiar(event):
    actor = get_actor(event, require_user=True)
    order_id = get_order_id(event)
    data = read_body(event)
    if set(data) - {"action", "reason"}:
        raise ApiError(400, "Campos no permitidos")
    action = data.get("action")
    if action not in TRANSITIONS:
        raise ApiError(400, "action no es válida")
    reason = ""
    if data.get("reason"):
        reason = clean_text(data.get("reason"), 3, 200)
        if reason is None:
            raise ApiError(400, "reason debe tener entre 3 y 200 caracteres")

    order = load_order(order_id)
    if order is None or not can_see_order(order, actor):
        raise ApiError(404, "Pedido no encontrado")
    header = order["header"]
    who = _role_in_order(header, actor)
    rule = TRANSITIONS[action]
    allowed_from = rule["from"].get(who)
    if allowed_from is None:
        raise ApiError(403, "No puedes hacer esta acción en este pedido")
    current = header.get("status")
    if current not in allowed_from:
        raise ApiError(409, f"El pedido está en {current}; no se puede {action}")

    now, target, pk = now_iso(), rule["to"], f"ORDER#{order_id}"
    values = {":to": target, ":from": current, ":now": now,
              ":g2": f"STATUS#{target}", ":g2s": f"{now}#{order_id}"}
    expression = "SET #st = :to, updated_at = :now, GSI2PK = :g2, GSI2SK = :g2s"
    if reason:
        expression += ", status_reason = :r"
        values[":r"] = reason
    operations = [
        {"Update": {"TableName": ORDERS_TABLE, "Key": {"PK": pk, "SK": "ORDER"},
                    "UpdateExpression": expression,
                    "ConditionExpression": "#st = :from",
                    "ExpressionAttributeNames": {"#st": "status"},
                    "ExpressionAttributeValues": values}},
        {"Put": {"TableName": ORDERS_TABLE, "Item": {
            "PK": pk, "SK": status_sk(now, target), "entity": "StatusChange", "order_id": order_id,
            "status": target, "at": now, "by": who, "reason": reason}}},
    ]
    if action in ("ship", "deliver"):
        field = "shipped_at" if action == "ship" else "delivered_at"
        operations.append({"Update": {"TableName": ORDERS_TABLE, "Key": {"PK": pk, "SK": "SHIPMENT"},
                                      "UpdateExpression": f"SET {field} = :now",
                                      "ExpressionAttributeValues": {":now": now}}})
    if action == "deliver":
        # Registro de compra entregada: es lo que permite publicar UNA reseña de ese producto.
        for item in order["items"]:
            operations.append({"Update": {
                "TableName": COMMUNITY_TABLE,
                "Key": {"PK": f"USER#{header['buyer_id']}", "SK": f"PURCHASED#{item['product_id']}"},
                "UpdateExpression": "SET #ent = :e, product_id = :p, order_id = :o, delivered_at = :now",
                "ExpressionAttributeNames": {"#ent": "entity"},
                "ExpressionAttributeValues": {":e": "Purchase", ":p": item["product_id"],
                                              ":o": order_id, ":now": now},
            }})
    if action == "cancel":
        existing = batch_get_products(item["product_id"] for item in order["items"])
        for item in order["items"]:
            if item["product_id"] in existing:
                operations.append({"Update": {
                    "TableName": PRODUCTS_TABLE, "Key": {"product_id": item["product_id"]},
                    "UpdateExpression": "SET stock = stock + :q, updated_at = :now",
                    "ConditionExpression": "attribute_exists(product_id)",
                    "ExpressionAttributeValues": {":q": int(item["quantity"]), ":now": now},
                }})
    try:
        transact(operations)
    except ClientError as error:
        if cancellation_codes(error) is not None:
            raise ApiError(409, "El pedido cambió mientras tanto. Recarga la página.")
        raise
    return respuesta(200, {"mensaje": "Pedido actualizado",
                           "pedido": order_detail(load_order(order_id), actor)})


def lambda_handler(event, context):
    return run(_cambiar, event, context)
