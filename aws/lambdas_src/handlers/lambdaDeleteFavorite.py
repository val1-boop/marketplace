"""Lambda lambdaDeleteFavorite: DELETE /favorites/{product_id} - quita un favorito.

Ruta: DELETE /favorites/{product_id}   ·  Autorizador: mktTokenAuthorizer
Tabla: Community. Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaDeleteFavorite


def _quitar(event):
    actor = get_actor(event, require_user=True)
    product_id = get_product_id(event)
    COMMUNITY.delete_item(Key={"PK": actor.user_key, "SK": f"FAV#{product_id}"})
    return respuesta(200, {"mensaje": "Quitado de favoritos", "product_id": product_id})


def lambda_handler(event, context):
    return run(_quitar, event, context)
