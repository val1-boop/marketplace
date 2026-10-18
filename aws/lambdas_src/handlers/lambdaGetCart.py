"""Lambda lambdaGetCart: GET /cart - el carrito de quien llama, con precios y existencias ACTUALES.

Ruta: GET /cart   ·  Autorizador: mktTokenAuthorizer
Tablas: Marketplace (USER#<id> / CART#<producto>) y Products. Sin variables de entorno
(usa los nombres de la Parte 5). Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaGetCart
# GET /cart  ->  {"lineas": [{producto, cantidad, disponible, motivo}], "total": "0.00"}


def cart_lines(actor):
    rows = query_all(
        MARKETPLACE,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :cart)",
        ExpressionAttributeValues={":pk": actor.user_key, ":cart": "CART#"},
    )
    products = batch_get_products(row["product_id"] for row in rows)
    lines, total = [], Decimal("0")
    for row in rows:
        quantity = int(row.get("quantity", 1))
        item = products.get(row["product_id"])
        reason = ""
        if item is None:
            reason = "Ya no existe"
        elif item.get("status") != "ACTIVE":
            reason = "No disponible"
        elif int(item.get("stock", 0)) < quantity:
            reason = "Sin existencias suficientes"
        available = reason == ""
        line = {
            "product_id": row["product_id"],
            "quantity": quantity,
            "available": available,
            "reason": reason,
            "added_at": row.get("added_at", ""),
            # El precio SIEMPRE es el actual de Products, nunca el que se guardó al agregar.
            "producto": public(item) if item else None,
        }
        if available:
            total += Decimal(item["price"]) * quantity
        lines.append(line)
    lines.sort(key=lambda line: line["added_at"])
    return lines, total


def _ver(event):
    actor = get_actor(event, require_user=True)
    if actor.role != "user":
        raise ApiError(403, "Solo los usuarios compran")
    lines, total = cart_lines(actor)
    return respuesta(200, {"lineas": lines, "total": money(total)})


def lambda_handler(event, context):
    return run(_ver, event, context)
