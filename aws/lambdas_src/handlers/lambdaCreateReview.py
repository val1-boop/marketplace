"""Lambda lambdaCreateReview: POST /products/{product_id}/reviews - publica una reseña con estrellas.

Ruta: POST /products/{product_id}/reviews   ·  Autorizador: mktTokenAuthorizer
Cuerpo: {"rating": 1..5, "comment": "10 a 1000 caracteres", "author_name": "Ana P."}
Tablas: Community y Products. Sin variables de entorno. Python 3.14, rol LabRole, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).

En UNA transacción: (1) marca la compra entregada como "ya opinó" (si no existe la compra o ya
opinó, se cancela todo), (2) guarda la reseña y (3) suma la calificación al producto
(rating_sum, rating_count y el contador de esa estrella), de donde sale el promedio.
"""
# ---------------------------------------------------------------- lambdaCreateReview


def _opinar(event):
    actor = get_actor(event, require_user=True)
    if actor.role != "user":
        raise ApiError(403, "Solo los compradores pueden opinar")
    product_id = get_product_id(event)
    data = read_body(event)
    if set(data) - {"rating", "comment", "author_name"}:
        raise ApiError(400, "Campos no permitidos")
    raw_rating = data.get("rating")
    # Solo un número JSON entero (no texto, no decimales, no true/false).
    rating = parse_int(raw_rating, 1, 5) if isinstance(raw_rating, int) and not isinstance(raw_rating, bool) else None
    comment = clean_text(data.get("comment"), 10, 1000, allow_newlines=True)
    author = clean_text(data.get("author_name"), 2, 40)
    errors = []
    if rating is None:
        errors.append("rating debe ser un entero de 1 a 5")
    if comment is None:
        errors.append("comment debe tener entre 10 y 1000 caracteres")
    if author is None or not DISPLAY_NAME_RE.match(author):
        errors.append("author_name no es válido")
    if errors:
        raise ApiError(400, "Datos inválidos", errors)

    review_id, now = new_ulid(), now_iso()
    operations = [
        {"Update": {
            "TableName": COMMUNITY_TABLE,
            "Key": {"PK": actor.user_key, "SK": f"PURCHASED#{product_id}"},
            "UpdateExpression": "SET reviewed = :t, review_id = :rid",
            "ConditionExpression": "attribute_exists(PK) AND attribute_not_exists(reviewed)",
            "ExpressionAttributeValues": {":t": True, ":rid": review_id},
        }},
        {"Put": {"TableName": COMMUNITY_TABLE, "ConditionExpression": "attribute_not_exists(PK)", "Item": {
            "PK": f"PRODUCT#{product_id}", "SK": f"REVIEW#{review_id}", "entity": "Review",
            "review_id": review_id, "product_id": product_id, "rating": rating, "comment": comment,
            "author_name": author, "status": "VISIBLE", "created_at": now,
            "GSI1PK": actor.user_key, "GSI1SK": f"REVIEW#{review_id}",
        }}},
        {"Update": {
            "TableName": PRODUCTS_TABLE, "Key": {"product_id": product_id},
            "UpdateExpression": f"ADD rating_sum :r, rating_count :one, rating_{rating} :one",
            "ConditionExpression": "attribute_exists(product_id)",
            "ExpressionAttributeValues": {":r": rating, ":one": 1},
        }},
    ]
    try:
        transact(operations)
    except ClientError as error:
        codes = cancellation_codes(error)
        if codes is None:
            raise
        if codes and codes[0] == "ConditionalCheckFailed":
            raise ApiError(403, "Solo puedes opinar una vez sobre productos que compraste y recibiste")
        raise ApiError(404, "Producto no encontrado")
    return respuesta(201, {"mensaje": "Gracias por tu opinión", "review_id": review_id})


def lambda_handler(event, context):
    return run(_opinar, event, context)
