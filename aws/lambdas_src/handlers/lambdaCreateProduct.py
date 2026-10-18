"""Lambda lambdaCreateProduct: POST /products - publica un producto (solo vendedores).

Ruta: POST /products   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaCreateProduct
# POST /products   (solo un vendedor; el seller_id sale de la sesión de Flask)


def _crear(event):
    actor = get_actor(event)
    if actor.role != "user":
        raise ApiError(403, "Solo los vendedores pueden publicar productos")
    product = validate_product(read_body(event))
    now = now_iso()
    for _ in range(5):
        # El identificador lo genera el servidor; nunca viene del cliente.
        item = dict(product)
        item.update({
            "product_id": f"PROD-{secrets.randbelow(10**8):08d}",
            "listed_category": product["category"],
            "seller_id": actor.seller_id,
            "status": "ACTIVE",
            "sales_count": 0,
            "rating_sum": 0,
            "rating_count": 0,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })
        try:
            TABLE.put_item(Item=item, ConditionExpression="attribute_not_exists(product_id)")
        except ClientError as error:
            if is_conditional_failure(error):
                continue  # colisión de ID: se genera otro
            raise
        return respuesta(201, {"mensaje": "Producto creado", "producto": public(item)})
    raise ApiError(500, "No fue posible generar un identificador")


def lambda_handler(event, context):
    return run(_crear, event, context)
