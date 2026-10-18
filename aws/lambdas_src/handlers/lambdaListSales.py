"""Lambda lambdaListSales: GET /sales - "Mis ventas" (pedidos que recibió el vendedor).

Ruta: GET /sales   ·  Autorizador: mktTokenAuthorizer
Tabla: Orders, índice GSI1 (GSI1PK = SELLER#<vendedor> en los renglones). Sin variables de
entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaListSales
MAX_ROWS = 300


def _listar(event):
    actor = get_actor(event, require_user=True)
    if actor.role != "user":
        raise ApiError(403, "Solo los vendedores tienen ventas")
    rows = query_all(
        ORDERS,
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :s AND begins_with(GSI1SK, :o)",
        ExpressionAttributeValues={":s": f"SELLER#{actor.seller_id}", ":o": "ORDER#"},
        ScanIndexForward=False,
        Limit=MAX_ROWS,
    )
    order_ids = list(dict.fromkeys(r["order_id"] for r in rows))[:100]
    headers = []
    if order_ids:
        keys = [{"PK": f"ORDER#{oid}", "SK": "ORDER"} for oid in order_ids]
        result = DYNAMO.batch_get_item(RequestItems={ORDERS_TABLE: {"Keys": keys}})
        headers = result.get("Responses", {}).get(ORDERS_TABLE, [])
    sales = sorted((order_summary(h) for h in headers if h.get("seller_id") == actor.seller_id),
                   key=lambda o: o["order_id"], reverse=True)
    return respuesta(200, {"ventas": sales})


def lambda_handler(event, context):
    return run(_listar, event, context)
