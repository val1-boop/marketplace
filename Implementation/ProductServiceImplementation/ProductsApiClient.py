"""Operaciones de PRODUCTOS sobre el API Gateway: Flask → API Gateway → Lambda → DynamoDB Products.

La conexión (token, timeout, errores) está en SharedImplementation/ApiGatewayClient.py; aquí
solo se arman las rutas de productos. Los IDs se validan con lista blanca ANTES de construir
la ruta (sin path traversal) y solo viajan los campos editables (sin mass assignment).
"""
from urllib.parse import quote

from Implementation.SharedImplementation.ApiGatewayClient import ApiGatewayClient
from Interfaces.ProductServiceInterface.ProductDTO import Product, ProductDTO  # noqa: F401
from Interfaces.ProductServiceInterface.ProductErrors import (  # noqa: F401  (se re-exportan)
    ProductConflict,
    ProductForbidden,
    ProductNotFound,
    ProductsAPIError,
    ProductValidationError,
)
from Security import PRODUCT_ID_RE, SELLER_ID_RE


class ProductsAPI(ApiGatewayClient):
    @staticmethod
    def _path(product_id, suffix=""):
        if not isinstance(product_id, str) or not PRODUCT_ID_RE.match(product_id):
            raise ProductNotFound("ID inválido")
        return "/products/" + quote(product_id, safe="") + suffix

    PAGE_SIZE = 500   # productos por llamada (cada llamada es una invocación de Lambda)
    MAX_PAGES = 100   # tope de seguridad: 50,000 productos

    def list_products(self, seller_id=None):
        """Todos los productos (o los de un vendedor), pidiendo el API por páginas."""
        params = {"limit": self.PAGE_SIZE}
        if seller_id is not None:
            if not SELLER_ID_RE.match(seller_id):
                return []
            params["seller_id"] = seller_id
        products = []
        for _ in range(self.MAX_PAGES):
            body = self.request("GET", "/products", params=params)
            items = body.get("productos")
            if not isinstance(items, list):
                raise ProductsAPIError("Listado inesperado")
            products.extend(ProductDTO.from_api(item) for item in items)
            cursor = body.get("next_cursor")
            if not cursor:
                return products
            params = {**params, "cursor": str(cursor)[:400]}
        raise ProductsAPIError("El catálogo tiene demasiadas páginas")

    def get_product(self, product_id):
        body = self.request("GET", self._path(product_id))
        return ProductDTO.from_api(body.get("producto") or {})

    def create_product(self, seller_id, data):
        body = self.request("POST", "/products", json=self._payload(data), actor=("user", seller_id))
        return ProductDTO.from_api(body.get("producto") or {})

    def update_product(self, product_id, seller_id, data, expected_version):
        payload = self._payload(data)
        payload.update({"action": "update", "expected_version": int(expected_version)})
        body = self.request("PUT", self._path(product_id), json=payload, actor=("user", seller_id))
        return ProductDTO.from_api(body.get("producto") or {})

    def moderate_product(self, product_id, action, reason=None):
        payload = {"action": action}
        if reason is not None:
            payload["reason"] = reason
        body = self.request("PUT", self._path(product_id), json=payload, actor=("admin", ""))
        return ProductDTO.from_api(body.get("producto") or {})

    def delete_product(self, product_id, role, seller_id):
        self.request("DELETE", self._path(product_id), actor=(role, seller_id))

    @staticmethod
    def _payload(data):
        """Solo los campos editables; el precio viaja como texto para no perder decimales."""
        if hasattr(data, "as_dict"):
            data = data.as_dict()
        payload = {
            "name": data["name"],
            "category": data["category"],
            "price": str(data["price"]),
            "stock": int(data["stock"]),
            "condition": data["condition"],
        }
        if data.get("description") is not None:
            payload["description"] = data["description"]
        if data.get("seller_sku"):
            payload["seller_sku"] = data["seller_sku"]
        return payload
