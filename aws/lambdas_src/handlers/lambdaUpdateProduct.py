"""Lambda lambdaUpdateProduct: PUT /products/{product_id} - edita (dueño) o modera (admin) un producto.

Ruta: PUT /products/{product_id}   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaUpdateProduct
# PUT /products/{product_id}
#   {"action": "update", "expected_version": 3, "name": ..., ...}  -> el dueño edita
#   {"action": "block", "reason": "..."}                         -> admin bloquea
#   {"action": "unblock"}                                        -> admin desbloquea
#   {"action": "delist"}                                         -> admin retira (baja de vendedor)


def _update(product_id, item, role, seller_id, data):
    if role != "user" or item.get("seller_id") != seller_id:
        raise ApiError(403, "No puedes modificar este producto")
    if item.get("status") == "DELISTED":
        raise ApiError(404, "Producto no encontrado")
    expected = parse_int(data.get("expected_version"), 1, 10**9)
    if expected is None:
        raise ApiError(400, "expected_version es obligatorio")
    product = validate_product(data, allowed_extra=("action", "expected_version"))
    values = {
        ":n": product["name"], ":sn": product["search_name"], ":d": product["description"],
        ":c": product["category"],
        ":p": product["price"], ":s": product["stock"], ":cd": product["condition"],
        ":u": now_iso(), ":one": 1, ":sid": seller_id, ":v": expected,
    }
    expression = ("SET #n = :n, search_name = :sn, description = :d, category = :c, price = :p, stock = :s, "
                  "#cond = :cd, updated_at = :u, #ver = #ver + :one")
    if item.get("status") == "ACTIVE":
        expression += ", listed_category = :c"
    try:
        result = TABLE.update_item(
            Key={"product_id": product_id},
            UpdateExpression=expression,
            # Atómico: solo si sigue siendo del vendedor y nadie lo cambió desde que se leyó.
            ConditionExpression="seller_id = :sid AND #ver = :v",
            ExpressionAttributeNames=names_for(expression, "#ver = :v"),
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if is_conditional_failure(error):
            raise ApiError(409, "El producto cambió mientras lo editabas")
        raise
    return respuesta(200, {"mensaje": "Producto actualizado", "producto": public(result["Attributes"])})


def _moderate(product_id, item, role, data):
    if role != "admin":
        raise ApiError(403, "Solo un administrador puede moderar productos")
    action = data.get("action")
    if set(data) - {"action", "reason"}:
        raise ApiError(400, "Campos no permitidos")
    now = now_iso()
    if action == "block":
        reason = data.get("reason")
        reason = unicodedata.normalize("NFC", reason).strip() if isinstance(reason, str) else ""
        if not 5 <= len(reason) <= 500 or any(unicodedata.category(c).startswith("C") for c in reason):
            raise ApiError(400, "reason debe tener entre 5 y 500 caracteres")
        expression = ("SET #st = :blocked, blocked_reason = :r, prior_status = :active, "
                      "updated_at = :u, #ver = #ver + :one REMOVE listed_category")
        condition = "#st = :active"
        values = {":blocked": "BLOCKED", ":active": "ACTIVE", ":r": reason, ":u": now, ":one": 1}
    elif action == "unblock":
        expression = ("SET #st = :active, listed_category = category, updated_at = :u, "
                      "#ver = #ver + :one REMOVE blocked_reason, prior_status")
        condition = "#st = :blocked"
        values = {":blocked": "BLOCKED", ":active": "ACTIVE", ":u": now, ":one": 1}
    elif action == "delist":
        expression = "SET #st = :delisted, updated_at = :u, #ver = #ver + :one REMOVE listed_category"
        condition = "attribute_exists(product_id)"
        values = {":delisted": "DELISTED", ":u": now, ":one": 1}
    else:
        raise ApiError(400, "action no es válida")
    try:
        result = TABLE.update_item(
            Key={"product_id": product_id},
            UpdateExpression=expression,
            ConditionExpression=condition,
            ExpressionAttributeNames=names_for(expression, condition),
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if is_conditional_failure(error):
            raise ApiError(409, "El estado actual del producto no permite esa acción")
        raise
    return respuesta(200, {"mensaje": "Producto actualizado", "producto": public(result["Attributes"])})


def _modificar(event):
    product_id = get_product_id(event)
    actor = get_actor(event)
    role, seller_id = actor.role, actor.seller_id
    data = read_body(event)
    item = TABLE.get_item(Key={"product_id": product_id}).get("Item")
    if item is None:
        raise ApiError(404, "Producto no encontrado")
    if data.get("action", "update") == "update":
        return _update(product_id, item, role, seller_id, data)
    return _moderate(product_id, item, role, data)


def lambda_handler(event, context):
    return run(_modificar, event, context)
