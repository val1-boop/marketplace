"""Lambda lambdaAddFavorite: PUT /favorites/{product_id} - marca un producto como favorito.

Ruta: PUT /favorites/{product_id}   ·  Autorizador: mktTokenAuthorizer
Tablas: Community y Products. Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaAddFavorite


def _agregar(event):
    actor = get_actor(event, require_user=True)
    product_id = get_product_id(event)
    product = TABLE.get_item(Key={"product_id": product_id}).get("Item")
    if product is None or product.get("status") != "ACTIVE":
        raise ApiError(404, "Producto no encontrado")
    key = {"PK": actor.user_key, "SK": f"FAV#{product_id}"}
    if COMMUNITY.get_item(Key=key).get("Item") is None:
        count = COMMUNITY.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :fav)",
            ExpressionAttributeValues={":pk": actor.user_key, ":fav": "FAV#"},
            Select="COUNT",
        ).get("Count", 0)
        if count >= FAVORITES_MAX:
            raise ApiError(409, f"Máximo {FAVORITES_MAX} favoritos")
        COMMUNITY.put_item(Item={**key, "entity": "Favorite", "product_id": product_id,
                                 "created_at": now_iso()})
    return respuesta(200, {"mensaje": "Agregado a favoritos", "product_id": product_id})


def lambda_handler(event, context):
    return run(_agregar, event, context)
