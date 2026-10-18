"""Lambda lambdaListReviews: GET /products/{product_id}/reviews - opiniones de un producto.

Ruta: GET /products/{product_id}/reviews   ·  Autorizador: mktTokenAuthorizer
Tabla: Community (PRODUCT#<p> / REVIEW#<ulid>, y USER#<id> / PURCHASED#<p>). Sin variables de
entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).

Si quien pide trae su usuario (sesión iniciada en Flask), la respuesta dice además si puede
opinar: solo quien recibió el producto y todavía no ha opinado.
"""
# ---------------------------------------------------------------- lambdaListReviews
MAX_REVIEWS = 50


def _listar(event):
    product_id = get_product_id(event)
    rows = query_all(
        COMMUNITY,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :r)",
        ExpressionAttributeValues={":pk": f"PRODUCT#{product_id}", ":r": "REVIEW#"},
        ScanIndexForward=False,  # ULID: la más reciente primero
        Limit=MAX_REVIEWS,
    )
    reviews = [{
        "rating": int(r.get("rating", 0)),
        "comment": r.get("comment", ""),
        "author_name": r.get("author_name", ""),
        "created_at": r.get("created_at", ""),
        "verified": True,  # solo se aceptan reseñas de compras entregadas
    } for r in rows if r.get("status", "VISIBLE") == "VISIBLE"]
    can_review = False
    actor = get_optional_actor(event)
    if actor is not None and actor.role == "user":
        purchase = COMMUNITY.get_item(Key={"PK": actor.user_key, "SK": f"PURCHASED#{product_id}"}).get("Item")
        can_review = purchase is not None and not purchase.get("reviewed")
    return respuesta(200, {"resenas": reviews, "puede_opinar": can_review})


def lambda_handler(event, context):
    return run(_listar, event, context)
