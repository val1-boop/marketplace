"""Lambda lambdaDeleteProduct: DELETE /products/{product_id} - elimina un producto (dueño o admin).

Ruta: DELETE /products/{product_id}   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaDeleteProduct
# DELETE /products/{product_id}   (el dueño, o un administrador como moderación)


def _eliminar(event):
    product_id = get_product_id(event)
    actor = get_actor(event)
    kwargs = {"Key": {"product_id": product_id}}
    if actor.role == "admin":
        kwargs["ConditionExpression"] = "attribute_exists(product_id)"
    else:
        # Atómico: DynamoDB solo borra si el producto es de este vendedor (anti IDOR).
        kwargs["ConditionExpression"] = "attribute_exists(product_id) AND seller_id = :sid"
        kwargs["ExpressionAttributeValues"] = {":sid": actor.seller_id}
    try:
        TABLE.delete_item(**kwargs)
    except ClientError as error:
        if not is_conditional_failure(error):
            raise
        exists = TABLE.get_item(Key={"product_id": product_id}).get("Item") is not None
        if exists:
            raise ApiError(403, "No puedes eliminar este producto")
        raise ApiError(404, "Producto no encontrado")
    return respuesta(200, {"mensaje": "Producto eliminado", "product_id": product_id})


def lambda_handler(event, context):
    return run(_eliminar, event, context)
