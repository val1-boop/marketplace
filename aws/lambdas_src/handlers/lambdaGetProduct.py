"""Lambda lambdaGetProduct: GET /products/{product_id} - consulta un producto.

Ruta: GET /products/{product_id}   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaGetProduct
# GET /products/{product_id}


def _obtener(event):
    product_id = get_product_id(event)
    item = TABLE.get_item(Key={"product_id": product_id}).get("Item")
    if item is None:
        raise ApiError(404, "Producto no encontrado")
    return respuesta(200, {"producto": public(item)})


def lambda_handler(event, context):
    return run(_obtener, event, context)
