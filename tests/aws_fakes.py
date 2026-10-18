"""Simulación local de DynamoDB y API Gateway para probar sin AWS.

- FakeDynamo tiene las 4 tablas de la Parte 5 (Products, Orders, Marketplace, Community) con
  sus índices, y entiende el subconjunto de expresiones que usan las Lambdas: condiciones
  (attribute_exists, =, <>, >=, <=, >, <, AND), SET (con +, - e if_not_exists), ADD, REMOVE,
  consultas por clave (=, begins_with) en tabla e índices, BatchGetItem y TransactWriteItems
  (todo o nada, con CancellationReasons como AWS).
- Igual que DynamoDB: los números se guardan como Decimal y un float se rechaza.
- load_lambdas() importa el código REAL de aws/lambdas/ con un boto3 falso.
- FakeApiGateway se usa como sesión de `requests` en el cliente de Flask: aplica el
  autorizador y enruta cada petición a la Lambda correspondiente, igual que AWS.
"""
import copy
import importlib.util
import json
import re
import sys
import types
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

LAMBDA_DIR = Path(__file__).resolve().parent.parent / "aws" / "lambdas"
LAMBDA_NAMES = sorted(p.stem for p in LAMBDA_DIR.glob("lambda*.py"))

PRODUCTS_SCHEMA = {"keys": ("product_id",), "indexes": {
    "bySeller": ("seller_id", "product_id"), "byCategoryPrice": ("listed_category", "price")}}
PK_SK_SCHEMA = {"keys": ("PK", "SK"), "indexes": {"GSI1": ("GSI1PK", "GSI1SK"), "GSI2": ("GSI2PK", "GSI2SK")}}
TABLE_SCHEMAS = {
    "Products": PRODUCTS_SCHEMA,
    "Orders": PK_SK_SCHEMA,
    "Marketplace": {"keys": ("PK", "SK"), "indexes": {}},
    "Community": PK_SK_SCHEMA,
}


class ClientError(Exception):
    def __init__(self, error_response, operation_name):
        super().__init__(f"{operation_name}: {error_response['Error']['Code']}")
        self.response = error_response


class _ConditionFailed(Exception):
    pass


def _conditional_failure(operation):
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, operation)


def _to_dynamo(value):
    """Como boto3: int → Decimal; float → error; recursivo en listas y mapas."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, Decimal)):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        raise TypeError("Float types are not supported. Use Decimal types instead.")
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dynamo(v) for v in value]
    raise TypeError(f"Tipo no soportado por DynamoDB: {type(value)!r}")


def _split_top(text, sep=","):
    """Divide por `sep` ignorando lo que esté entre paréntesis."""
    parts, depth, current = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


def _check_placeholders(names, values, *expressions):
    """Como DynamoDB real: todo #nombre y :valor enviado debe usarse en alguna expresión,
    y todo el que se use debe venir definido. Si no, ValidationException (la Lambda da 500)."""
    text = " ".join(e for e in expressions if e)
    used_names = set(re.findall(r"#[A-Za-z0-9_]+", text))
    used_values = set(re.findall(r":[A-Za-z0-9_]+", text))
    problems = []
    if set(names or {}) - used_names:
        problems.append(f"ExpressionAttributeNames sin usar: {sorted(set(names) - used_names)}")
    if set(values or {}) - used_values:
        problems.append(f"ExpressionAttributeValues sin usar: {sorted(set(values) - used_values)}")
    if used_names - set(names or {}):
        problems.append(f"Nombres sin definir: {sorted(used_names - set(names or {}))}")
    if used_values - set(values or {}):
        problems.append(f"Valores sin definir: {sorted(used_values - set(values or {}))}")
    if problems:
        raise ClientError({"Error": {"Code": "ValidationException", "Message": "; ".join(problems)}}, "Validate")


class _Expr:
    def __init__(self, names, values):
        self.names = names or {}
        self.values = {k: _to_dynamo(v) for k, v in (values or {}).items()}

    def attr(self, token):
        token = token.strip()
        if token.startswith("#"):
            return self.names[token]
        assert not token.startswith(":"), f"Se esperaba un atributo: {token}"
        return token

    def operand(self, token, item):
        token = token.strip()
        match = re.fullmatch(r"if_not_exists\((.+),(.+)\)", token)
        if match:
            name = self.attr(match.group(1))
            return item[name] if item is not None and name in item else self.operand(match.group(2), item)
        if token.startswith(":"):
            return self.values[token]
        name = self.attr(token)
        if item is None or name not in item:
            raise _ConditionFailed(f"Atributo inexistente en la expresión: {name}")
        return item[name]

    # ------------------------------------------------------------ condiciones
    def check(self, item, condition):
        if not condition:
            return True
        for clause in condition.split(" AND "):
            clause = clause.strip()
            match = re.fullmatch(r"attribute_(not_)?exists\((.+)\)", clause)
            if match:
                present = item is not None and self.attr(match.group(2)) in item
                if present == bool(match.group(1)):
                    return False
                continue
            match = re.fullmatch(r"begins_with\((.+),(.+)\)", clause)
            if match:
                if item is None:
                    return False
                value = item.get(self.attr(match.group(1)))
                if not isinstance(value, str) or not value.startswith(self.operand(match.group(2), item)):
                    return False
                continue
            match = re.fullmatch(r"(\S+) (=|<>|>=|<=|>|<) (\S+)", clause)
            if not match:
                raise AssertionError(f"Condición no soportada por FakeDynamo: {clause}")
            if item is None:
                return False
            try:
                left = self.operand(match.group(1), item)
            except _ConditionFailed:
                return False
            right = self.operand(match.group(3), item)
            op = match.group(2)
            result = {"=": left == right, "<>": left != right, ">=": left >= right,
                      "<=": left <= right, ">": left > right, "<": left < right}[op]
            if not result:
                return False
        return True

    # ------------------------------------------------------------ actualizaciones
    def apply(self, item, expression):
        sections = re.split(r"\b(SET|ADD|REMOVE)\b", expression.strip())
        assert sections[0].strip() == "", f"UpdateExpression no soportada: {expression}"
        for keyword, body in zip(sections[1::2], sections[2::2]):
            for part in _split_top(body):
                if keyword == "SET":
                    left, right = (p.strip() for p in part.split("=", 1))
                    name = self.attr(left)
                    match = re.fullmatch(r"(.+?)\s*([+-])\s*(.+)", right)
                    if match:
                        a = self.operand(match.group(1), item)
                        b = self.operand(match.group(3), item)
                        item[name] = a + b if match.group(2) == "+" else a - b
                    else:
                        item[name] = copy.deepcopy(self.operand(right, item))
                elif keyword == "ADD":
                    name, value = part.split()
                    item[self.attr(name)] = item.get(self.attr(name), Decimal(0)) + self.values[value]
                else:
                    item.pop(self.attr(part), None)
        return item


class FakeTable:
    def __init__(self, name="Products"):
        self.name = name
        schema = TABLE_SCHEMAS[name]
        self.keys = schema["keys"]
        self.indexes = schema["indexes"]
        self.items = {}
        self.calls = []

    # ------------------------------------------------------------ claves
    def _key(self, key):
        assert set(key) == set(self.keys), f"Clave inválida para {self.name}: {key}"
        return key[self.keys[0]] if len(self.keys) == 1 else tuple(key[k] for k in self.keys)

    def _key_of(self, item):
        return self._key({k: item[k] for k in self.keys})

    # ------------------------------------------------------------ API boto3
    def get_item(self, Key):
        self.calls.append("get_item")
        item = self.items.get(self._key(Key))
        return {"Item": copy.deepcopy(item)} if item is not None else {}

    def put_item(self, Item, ConditionExpression=None, ExpressionAttributeNames=None,
                 ExpressionAttributeValues=None):
        self.calls.append("put_item")
        _check_placeholders(ExpressionAttributeNames, ExpressionAttributeValues, ConditionExpression)
        expr = _Expr(ExpressionAttributeNames, ExpressionAttributeValues)
        key = self._key_of(Item)
        if not expr.check(self.items.get(key), ConditionExpression):
            raise _conditional_failure("PutItem")
        self.items[key] = _to_dynamo(copy.deepcopy(Item))
        return {}

    def delete_item(self, Key, ConditionExpression=None, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        self.calls.append("delete_item")
        _check_placeholders(ExpressionAttributeNames, ExpressionAttributeValues, ConditionExpression)
        expr = _Expr(ExpressionAttributeNames, ExpressionAttributeValues)
        key = self._key(Key)
        if not expr.check(self.items.get(key), ConditionExpression):
            raise _conditional_failure("DeleteItem")
        self.items.pop(key, None)
        return {}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None, ExpressionAttributeValues=None, ReturnValues=None):
        self.calls.append("update_item")
        _check_placeholders(ExpressionAttributeNames, ExpressionAttributeValues, UpdateExpression,
                            ConditionExpression)
        expr = _Expr(ExpressionAttributeNames, ExpressionAttributeValues)
        key = self._key(Key)
        current = self.items.get(key)
        if not expr.check(current, ConditionExpression):
            raise _conditional_failure("UpdateItem")
        item = copy.deepcopy(current) if current is not None else _to_dynamo(dict(Key))
        expr.apply(item, UpdateExpression)
        self.items[key] = item
        return {"Attributes": copy.deepcopy(item)} if ReturnValues == "ALL_NEW" else {}

    def scan(self, ExclusiveStartKey=None):
        self.calls.append("scan")
        return {"Items": [copy.deepcopy(i) for i in self.items.values()]}

    def query(self, KeyConditionExpression, ExpressionAttributeValues, IndexName=None,
              ExpressionAttributeNames=None, ScanIndexForward=True, Limit=None, Select=None,
              ExclusiveStartKey=None):
        self.calls.append(f"query:{IndexName or 'table'}")
        _check_placeholders(ExpressionAttributeNames, ExpressionAttributeValues, KeyConditionExpression)
        expr = _Expr(ExpressionAttributeNames, ExpressionAttributeValues)
        if IndexName:
            assert IndexName in self.indexes, f"{self.name} no tiene el índice {IndexName}"
            pk_name, sk_name = self.indexes[IndexName]
        else:
            pk_name, sk_name = self.keys[0], (self.keys[1] if len(self.keys) > 1 else None)
        clauses = [c.strip() for c in KeyConditionExpression.split(" AND ")]
        assert expr.attr(clauses[0].split("=")[0]) == pk_name, f"La partición debe ser {pk_name}"
        if len(clauses) > 1:
            assert sk_name and sk_name in clauses[1], f"La ordenación debe ser {sk_name}"
        rows = [i for i in self.items.values() if pk_name in i and expr.check(i, KeyConditionExpression)]
        rows.sort(key=lambda i: i.get(sk_name, "") if sk_name else "", reverse=not ScanIndexForward)
        if Limit:
            rows = rows[:Limit]
        if Select == "COUNT":
            return {"Count": len(rows), "Items": []}
        return {"Items": [copy.deepcopy(i) for i in rows], "Count": len(rows)}


class FakeDynamo:
    """boto3.resource("dynamodb") simulado, con las 4 tablas de la Parte 5."""

    def __init__(self, products=None):
        self.tables = {name: FakeTable(name) for name in TABLE_SCHEMAS}
        if products is not None:
            self.tables["Products"] = products
        self.meta = types.SimpleNamespace(client=types.SimpleNamespace(
            transact_write_items=self.transact_write_items))
        self.transactions = 0

    def Table(self, name):  # noqa: N802 (API de boto3)
        return self.tables[name]

    def batch_get_item(self, RequestItems):
        responses = {}
        for name, request in RequestItems.items():
            assert len(request["Keys"]) <= 100, "BatchGetItem admite máximo 100 claves"
            table = self.tables[name]
            responses[name] = [copy.deepcopy(table.items[table._key(k)])
                               for k in request["Keys"] if table._key(k) in table.items]
        return {"Responses": responses, "UnprocessedKeys": {}}

    def transact_write_items(self, TransactItems):
        assert len(TransactItems) <= 100, "TransactWriteItems admite máximo 100 operaciones"
        self.transactions += 1
        staged = {name: copy.deepcopy(t.items) for name, t in self.tables.items()}
        touched, reasons, failed = set(), [], False
        for operation in TransactItems:
            (kind, params), = operation.items()
            table = self.tables[params["TableName"]]
            if kind == "Put":
                key = table._key_of(params["Item"])
            else:
                key = table._key(params["Key"])
            ident = (table.name, key)
            assert ident not in touched, "Una transacción no puede tocar dos veces el mismo ítem"
            touched.add(ident)
            _check_placeholders(params.get("ExpressionAttributeNames"), params.get("ExpressionAttributeValues"),
                                params.get("UpdateExpression"), params.get("ConditionExpression"))
            expr = _Expr(params.get("ExpressionAttributeNames"), params.get("ExpressionAttributeValues"))
            current = staged[table.name].get(key)
            if not expr.check(current, params.get("ConditionExpression")):
                reasons.append({"Code": "ConditionalCheckFailed"})
                failed = True
                continue
            reasons.append({"Code": "None"})
            if kind == "Put":
                staged[table.name][key] = _to_dynamo(copy.deepcopy(params["Item"]))
            elif kind == "Delete":
                staged[table.name].pop(key, None)
            elif kind == "Update":
                item = copy.deepcopy(current) if current is not None else _to_dynamo(dict(params["Key"]))
                try:
                    expr.apply(item, params["UpdateExpression"])
                except _ConditionFailed:
                    reasons[-1] = {"Code": "ValidationError"}
                    failed = True
                    continue
                staged[table.name][key] = item
        if failed:
            raise ClientError({"Error": {"Code": "TransactionCanceledException"},
                               "CancellationReasons": reasons}, "TransactWriteItems")
        for name, items in staged.items():
            self.tables[name].items = items
        return {}


def _as_dynamo(table_or_dynamo):
    if isinstance(table_or_dynamo, FakeDynamo):
        return table_or_dynamo
    if table_or_dynamo is None:
        return FakeDynamo()
    dynamo = getattr(table_or_dynamo, "dynamo", None)
    if dynamo is None:
        dynamo = FakeDynamo(products=table_or_dynamo)
        table_or_dynamo.dynamo = dynamo
    return dynamo


def load_lambdas(table_or_dynamo, api_token):
    """Importa las Lambdas reales usando un boto3 falso que devuelve las tablas simuladas."""
    dynamo = _as_dynamo(table_or_dynamo)
    boto3 = types.ModuleType("boto3")
    boto3.resource = lambda service: dynamo
    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = ClientError
    botocore.exceptions = exceptions
    saved = {name: sys.modules.get(name) for name in ("boto3", "botocore", "botocore.exceptions")}
    sys.modules.update({"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions})
    import os
    previous = {k: os.environ.get(k) for k in ("TABLE_NAME", "API_TOKEN")}
    os.environ["TABLE_NAME"] = "Products"
    os.environ["API_TOKEN"] = api_token
    modules = {}
    try:
        for name in LAMBDA_NAMES:
            spec = importlib.util.spec_from_file_location(f"lambda_{name}", LAMBDA_DIR / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return modules


def make_event(method, path, headers=None, body=None, path_params=None, query=None):
    return {
        "version": "2.0",
        "rawPath": path,
        "headers": {k.lower(): v for k, v in (headers or {}).items()},
        "queryStringParameters": query or None,
        "pathParameters": path_params,
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {"http": {"method": method}, "requestId": "test"},
    }


class _Context:
    aws_request_id = "test-request-id"


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.content = body.encode("utf-8") if isinstance(body, str) else (body or b"")

    def json(self):
        return json.loads(self.content.decode("utf-8"))


P = r"(?P<product_id>[^/]+)"
O = r"(?P<order_id>[^/]+)"


class FakeApiGateway:
    """Se comporta como el API HTTP de AWS: autorizador + rutas + integraciones Lambda.
    Las rutas son EXACTAMENTE las de la sección 4.4 del README."""

    ROUTES = [
        ("GET", rf"^/products$", "lambdaListProducts"),
        ("POST", rf"^/products$", "lambdaCreateProduct"),
        ("GET", rf"^/products/{P}$", "lambdaGetProduct"),
        ("PUT", rf"^/products/{P}$", "lambdaUpdateProduct"),
        ("DELETE", rf"^/products/{P}$", "lambdaDeleteProduct"),
        ("GET", rf"^/products/{P}/reviews$", "lambdaListReviews"),
        ("POST", rf"^/products/{P}/reviews$", "lambdaCreateReview"),
        ("GET", r"^/cart$", "lambdaGetCart"),
        ("PUT", rf"^/cart/{P}$", "lambdaPutCartItem"),
        ("DELETE", rf"^/cart/{P}$", "lambdaDeleteCartItem"),
        ("GET", r"^/favorites$", "lambdaListFavorites"),
        ("PUT", rf"^/favorites/{P}$", "lambdaAddFavorite"),
        ("DELETE", rf"^/favorites/{P}$", "lambdaDeleteFavorite"),
        ("POST", r"^/orders$", "lambdaCreateOrder"),
        ("GET", r"^/orders$", "lambdaListOrders"),
        ("GET", rf"^/orders/{O}$", "lambdaGetOrder"),
        ("PUT", rf"^/orders/{O}$", "lambdaUpdateOrderStatus"),
        ("GET", r"^/sales$", "lambdaListSales"),
    ]

    def __init__(self, base_url, table_or_dynamo, api_token):
        self.base_path = urlsplit(base_url).path.rstrip("/")
        self.dynamo = _as_dynamo(table_or_dynamo)
        self.lambdas = load_lambdas(self.dynamo, api_token)
        self.routes = [(m, re.compile(p), n) for m, p, n in self.ROUTES]
        self.requests = []
        self.down = False

    def request(self, method, url, json=None, params=None, headers=None, timeout=None, allow_redirects=True):
        import json as jsonlib

        assert timeout is not None, "Toda llamada al API debe tener timeout"
        if self.down:
            from requests import ConnectionError as RequestsConnectionError  # noqa: N814
            raise RequestsConnectionError("API caído (simulado)")
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.requests.append((method, url, dict(headers)))
        path = urlsplit(url).path
        if not path.startswith(self.base_path):
            return FakeResponse(404, '{"message":"Not Found"}')
        path = path[len(self.base_path):] or "/"
        if "x-mkt-token" not in headers:
            return FakeResponse(401, '{"message":"Unauthorized"}')
        auth = self.lambdas["lambdaAuthorizer"].lambda_handler(
            make_event(method, path, headers), _Context())
        if not auth.get("isAuthorized"):
            return FakeResponse(403, '{"message":"Forbidden"}')
        for route_method, pattern, name in self.routes:
            match = pattern.match(path)
            if match and route_method == method:
                path_params = {k: unquote(v) for k, v in match.groupdict().items()} or None
                body = jsonlib.dumps(json) if json is not None else None
                event = make_event(method, path, headers, body, path_params, params)
                result = self.lambdas[name].lambda_handler(event, _Context())
                return FakeResponse(result["statusCode"], result["body"])
        return FakeResponse(404, '{"message":"Not Found"}')


def seed_item(table, product_id, name, seller_id, price="100.00", stock=5,
              category="computers", status="ACTIVE", description=""):
    import unicodedata
    table.items[product_id] = {
        "product_id": product_id, "name": name,
        "search_name": unicodedata.normalize("NFKC", name).casefold(),
        "description": description,
        "category": category, "listed_category": category if status == "ACTIVE" else None,
        "price": Decimal(price), "stock": Decimal(stock), "seller_id": seller_id,
        "condition": "NEW", "status": status, "version": Decimal(1), "sales_count": Decimal(0),
        "created_at": "2026-10-01T00:00:00.000Z", "updated_at": "2026-10-01T00:00:00.000Z",
    }
    if table.items[product_id]["listed_category"] is None:
        del table.items[product_id]["listed_category"]
