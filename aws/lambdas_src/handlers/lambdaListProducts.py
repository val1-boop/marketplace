"""Lambda lambdaListProducts: GET /products - lista todos los productos o los de un vendedor.

Ruta: GET /products y GET /products?seller_id=SEL-######   ·  Autorizador: mktTokenAuthorizer
Python 3.14, rol LabRole, variable de entorno TABLE_NAME=Products, timeout 10 s.
Se pega completo en lambda_function.py de la consola de Lambda (Deploy después).
"""
# ---------------------------------------------------------------- lambdaListProducts
# GET /products                 -> todos los productos (scan paginado)
# GET /products?seller_id=SEL-x -> productos de un vendedor (índice bySeller)
MAX_ITEMS = 1000


def _listar(event):
    params = event.get("queryStringParameters") or {}
    seller_id = params.get("seller_id")
    kwargs = {}
    if seller_id is not None:
        if not SELLER_ID_RE.match(seller_id):
            raise ApiError(400, "seller_id no es válido")
        operation = TABLE.query
        kwargs = {
            "IndexName": "bySeller",
            "KeyConditionExpression": "seller_id = :s",
            "ExpressionAttributeValues": {":s": seller_id},
        }
    else:
        operation = TABLE.scan
    items = []
    while True:
        page = operation(**kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key or len(items) >= MAX_ITEMS:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return respuesta(200, {"productos": [public(item) for item in items[:MAX_ITEMS]]})


def lambda_handler(event, context):
    return run(_listar, event, context)
