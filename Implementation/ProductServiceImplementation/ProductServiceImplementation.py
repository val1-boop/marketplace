"""Implementación del servicio de productos.

Reglas de negocio del catálogo (búsqueda, filtros, visibilidad, dueño) y llamadas al
API de productos (ProductsApiClient). Las rutas (Services/ProductService) solo llaman
a estos métodos; aquí vive la lógica, una sola vez.
"""
import threading
import time

from flask import current_app

from Core.Catalog import department_of
from Core.Extensions import db
from Implementation.SharedImplementation.AccountQueries import seller_display_names, user_id_of_seller
from Implementation.SharedImplementation.AuditLog import record_admin_action
from Interfaces.ProductServiceInterface.IProductService import IProductService
from Interfaces.ProductServiceInterface.ProductDTO import CatalogResultDTO, ProductDetailDTO
from Interfaces.ProductServiceInterface.ProductErrors import ProductForbidden, ProductNotFound
from Security import PRODUCT_ID_RE, normalize_search, security_log

# Orden del catálogo: lista blanca (el formulario solo acepta estas claves).
SORT_KEYS = {
    "newest": (lambda p: (p.created_at, p.product_id), True),
    "rating": (lambda p: (p.rating_avg, p.rating_count, p.product_id), True),
    "best_selling": (lambda p: (p.sales_count, p.rating_avg, p.product_id), True),
    "price_asc": (lambda p: (p.price, p.product_id), False),
    "price_desc": (lambda p: (p.price, p.product_id), True),
    "name": (lambda p: (p.name.casefold(), p.product_id), False),
}
RELATED_LIMIT = 4


def _matches(product, q):
    """Búsqueda literal (sin SQL, sin comodines ni expresiones regulares): nombre o código."""
    return normalize_search(q) in (product.search_name or normalize_search(product.name)) \
        or q.strip().upper() in product.product_id


class ProductServiceImplementation(IProductService):
    def __init__(self):
        # Caché corta del listado completo: el catálogo es público, así que muchas visitas
        # anónimas no se convierten en muchas llamadas a Lambda/DynamoDB (mitigación DoS).
        # Se vacía en cada escritura hecha desde esta app.
        self._lock = threading.Lock()
        self._cache = None
        self._cache_at = 0.0

    # ------------------------------------------------------------------ infraestructura
    @property
    def api(self):
        """Cliente registrado en create_app() (las pruebas lo sustituyen por uno simulado)."""
        return current_app.extensions["products_api"]

    def _invalidate(self):
        with self._lock:
            self._cache = None

    def invalidate_cache(self):
        """Lo llaman pedidos y reseñas: cambiaron existencias o calificaciones."""
        self._invalidate()

    def list_all_products(self):
        ttl = current_app.config.get("PRODUCT_LIST_CACHE_SECONDS", 0)
        if ttl > 0:
            with self._lock:
                if self._cache is not None and time.monotonic() - self._cache_at < ttl:
                    return list(self._cache)
        products = self.api.list_products()
        if ttl > 0:
            with self._lock:
                self._cache, self._cache_at = list(products), time.monotonic()
        return products

    # ------------------------------------------------------------------ lectura pública
    def list_active_products(self):
        return [p for p in self.list_all_products() if p.status == "ACTIVE"]

    def search_catalog(self, query):
        result = CatalogResultDTO()
        base = self.list_active_products()
        if query.q:
            base = [p for p in base if _matches(p, query.q)]
        # Contadores de los filtros, calculados sobre el resultado de la búsqueda de texto.
        for p in base:
            dept = department_of(p.category)
            result.facets["department"][dept] = result.facets["department"].get(dept, 0) + 1
            result.facets["category"][p.category] = result.facets["category"].get(p.category, 0) + 1
            result.facets["availability"][p.stock_state] = result.facets["availability"].get(p.stock_state, 0) + 1
        products = base
        if query.department:
            products = [p for p in products if department_of(p.category) == query.department]
        if query.category:
            products = [p for p in products if p.category == query.category]
        if query.availability:
            products = [p for p in products if p.stock_state == query.availability]
        key, reverse = SORT_KEYS[query.sort]
        products.sort(key=key, reverse=reverse)
        result.products = products
        return result

    def get_product(self, product_id, viewer):
        # El ID se valida ANTES de llamar al API: `../../etc/passwd` nunca sale de Flask.
        if not PRODUCT_ID_RE.match(product_id or ""):
            raise ProductNotFound("ID inválido")
        product = self.api.get_product(product_id)
        if product.status == "DELISTED" and not viewer.is_admin:
            raise ProductNotFound("Producto retirado")
        return product

    def get_product_detail(self, product_id, viewer):
        product = self.get_product(product_id, viewer)
        owner = self.is_owner(product, viewer)
        # Un producto bloqueado solo lo ven su dueño y los administradores.
        if product.status != "ACTIVE" and not (owner or viewer.is_admin):
            raise ProductNotFound("Producto no visible")
        related = []
        if product.status == "ACTIVE":
            related = [p for p in self.list_active_products()
                       if p.category == product.category and p.product_id != product.product_id][:RELATED_LIMIT]
        return ProductDetailDTO(
            product=product,
            related=related,
            seller_name=seller_display_names([product.seller_id]).get(product.seller_id),
            related_names=seller_display_names(p.seller_id for p in related),
            is_owner=owner,
            seller_user_id=user_id_of_seller(product.seller_id) if viewer.is_admin else None,
        )

    def seller_names(self, seller_ids):
        return seller_display_names(seller_ids)

    # ------------------------------------------------------------------ vendedor
    def is_owner(self, product, user):
        return bool(user.seller_id) and product.seller_id == user.seller_id

    def get_owned_product(self, product_id, user):
        product = self.get_product(product_id, user)
        if not self.is_owner(product, user):
            security_log("idor_blocked", user=user.id, product=product_id, op="edit")
            raise ProductForbidden("No eres el dueño")
        return product

    def list_seller_products(self, seller_id):
        products = [p for p in self.api.list_products(seller_id=seller_id) if p.status != "DELISTED"]
        products.sort(key=lambda p: p.updated_at, reverse=True)
        return products

    def search_seller_products(self, seller_id, q="", category="", status=""):
        products = self.list_seller_products(seller_id)
        if q:
            products = [p for p in products if _matches(p, q)]
        if category:
            products = [p for p in products if p.category == category]
        if status:
            products = [p for p in products if p.status == status]
        return products

    def create_product(self, seller_id, data):
        product = self.api.create_product(seller_id, data)
        self._invalidate()
        return product

    def update_product(self, product_id, seller_id, data, expected_version):
        product = self.api.update_product(product_id, seller_id, data, expected_version)
        self._invalidate()
        return product

    def can_delete(self, product, user):
        return self.is_owner(product, user) or user.is_admin

    def delete_product(self, product, user):
        owner = self.is_owner(product, user)
        if not (owner or user.is_admin):
            security_log("idor_blocked", user=user.id, product=product.product_id, op="delete")
            raise ProductForbidden("No autorizado")
        self.api.delete_product(product.product_id, "user" if owner else "admin", user.seller_id)
        self._invalidate()
        if not owner:
            record_admin_action(user, "delete_product", "product", product.product_id, "Eliminado por moderación")
            db.session.commit()
        return owner

    # ------------------------------------------------------------------ moderación
    def block_product(self, product_id, admin, reason):
        self.api.moderate_product(product_id, "block", reason)
        self._invalidate()
        record_admin_action(admin, "block_product", "product", product_id, reason)
        db.session.commit()

    def unblock_product(self, product_id, admin):
        self.api.moderate_product(product_id, "unblock")
        self._invalidate()
        record_admin_action(admin, "unblock_product", "product", product_id, "Desbloqueo por moderación")
        db.session.commit()

    def delist_seller_products(self, seller_id):
        for product in self.api.list_products(seller_id=seller_id):
            if product.status != "DELISTED":
                self.api.moderate_product(product.product_id, "delist")
        self._invalidate()

    def owns_listed_products(self, seller_id):
        """True si la tienda tiene productos no retirados (no se puede volver admin)."""
        if not seller_id:
            return False
        return any(p.status != "DELISTED" for p in self.api.list_products(seller_id=seller_id))
