"""Lambda lambdaDeleteCartItem: DELETE /cart/{product_id} - quita un producto del carrito.

Ruta: DELETE /cart/{product_id}   ·  Autorizador: mktTokenAuthorizer
Tabla: Marketplace. Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaDeleteCartItem


def _quitar(event):
    actor = get_actor(event, require_user=True)
    product_id = get_product_id(event)
    # La clave incluye el usuario de la sesión: nadie puede tocar el carrito de otro.
    MARKETPLACE.delete_item(Key={"PK": actor.user_key, "SK": f"CART#{product_id}"})
    return respuesta(200, {"mensaje": "Producto quitado del carrito", "product_id": product_id})


def lambda_handler(event, context):
    return run(_quitar, event, context)
