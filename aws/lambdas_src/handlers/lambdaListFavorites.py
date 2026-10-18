"""Lambda lambdaListFavorites: GET /favorites - los productos favoritos de quien llama.

Ruta: GET /favorites   ·  Autorizador: mktTokenAuthorizer
Tablas: Community (USER#<id> / FAV#<producto>) y Products. Sin variables de entorno.
Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaListFavorites


def _listar(event):
    actor = get_actor(event, require_user=True)
    rows = query_all(
        COMMUNITY,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :fav)",
        ExpressionAttributeValues={":pk": actor.user_key, ":fav": "FAV#"},
        Limit=FAVORITES_MAX,
    )
    rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    products = batch_get_products(row["product_id"] for row in rows)
    favorites = []
    for row in rows:
        item = products.get(row["product_id"])
        # Un producto borrado, bloqueado o retirado no se muestra (solo su ID, para poder quitarlo).
        visible = item is not None and item.get("status") == "ACTIVE"
        favorites.append({
            "product_id": row["product_id"],
            "added_at": row.get("created_at", ""),
            "producto": public(item) if visible else None,
        })
    return respuesta(200, {"favoritos": favorites})


def lambda_handler(event, context):
    return run(_listar, event, context)
