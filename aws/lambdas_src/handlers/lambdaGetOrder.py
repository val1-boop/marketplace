"""Lambda lambdaGetOrder: GET /orders/{order_id} - detalle de un pedido.

Ruta: GET /orders/{order_id}   ·  Autorizador: mktTokenAuthorizer
Tabla: Orders. Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).

Solo lo ven el comprador, el vendedor de ese pedido o un administrador. A cualquier otra
persona se le responde 404 (no 403), para no confirmar que el pedido existe (anti IDOR).
"""
# ---------------------------------------------------------------- lambdaGetOrder


def _ver(event):
    actor = get_actor(event, require_user=True)
    order_id = get_order_id(event)
    order = load_order(order_id)
    if order is None or not can_see_order(order, actor):
        raise ApiError(404, "Pedido no encontrado")
    return respuesta(200, {"pedido": order_detail(order, actor)})


def lambda_handler(event, context):
    return run(_ver, event, context)
