"""Lambda lambdaListOrders: GET /orders - "Mis pedidos" (los pedidos de quien compra).

Ruta: GET /orders   ·  Autorizador: mktTokenAuthorizer
Tabla: Orders, índice GSI1 (GSI1PK = USER#<comprador>). Sin variables de entorno.
Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaListOrders
MAX_ORDERS = 100


def _listar(event):
    actor = get_actor(event, require_user=True)
    headers = query_all(
        ORDERS,
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :u AND begins_with(GSI1SK, :o)",
        ExpressionAttributeValues={":u": actor.user_key, ":o": "ORDER#"},
        ScanIndexForward=False,  # los ID son ULID: el más reciente primero
        Limit=MAX_ORDERS,
    )
    orders = [order_summary(h) for h in headers if h.get("SK") == "ORDER"]
    return respuesta(200, {"pedidos": orders})


def lambda_handler(event, context):
    return run(_listar, event, context)
