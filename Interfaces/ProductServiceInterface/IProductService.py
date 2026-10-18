"""Contrato del servicio de productos.

Services/ProductService (las rutas) solo conoce esta interfaz; la implementación real
(Implementation/ProductServiceImplementation) habla con API Gateway → Lambda → DynamoDB.
"""
from abc import ABC, abstractmethod


class IProductService(ABC):
    # ----------------------------------------------------------- lectura (pública)
    @abstractmethod
    def list_all_products(self):
        """Todos los productos, incluidos bloqueados (estadísticas del administrador)."""

    @abstractmethod
    def list_active_products(self):
        """Productos en estado ACTIVE (portada y catálogo públicos)."""

    @abstractmethod
    def get_product(self, product_id, viewer):
        """El producto para operar sobre él; ProductNotFound si el ID es inválido, no existe
        o está retirado (DELISTED) y quien lo pide no es administrador."""

    @abstractmethod
    def search_catalog(self, query):
        """CatalogQueryDTO → CatalogResultDTO (búsqueda literal, filtros y orden)."""

    @abstractmethod
    def get_product_detail(self, product_id, viewer):
        """ProductDetailDTO, o ProductNotFound si no existe o el visitante no puede verlo."""

    @abstractmethod
    def seller_names(self, seller_ids):
        """{seller_id: "Nombre A."}: nombre público del vendedor, nunca su correo."""

    # ----------------------------------------------------------- vendedor
    @abstractmethod
    def is_owner(self, product, user):
        """True si `user` es el vendedor del producto."""

    @abstractmethod
    def get_owned_product(self, product_id, user):
        """El producto si `user` es su dueño; ProductForbidden si no (anti IDOR)."""

    @abstractmethod
    def list_seller_products(self, seller_id):
        """Productos de un vendedor (sin los retirados), del más reciente al más antiguo."""

    @abstractmethod
    def search_seller_products(self, seller_id, q="", category="", status=""):
        """Productos del vendedor filtrados por texto (nombre/código), categoría y estado.
        Reutiliza la misma búsqueda literal del catálogo; no llama al API más de una vez."""

    @abstractmethod
    def create_product(self, seller_id, data):
        """ProductInputDTO → ProductDTO. El seller_id sale de la sesión."""

    @abstractmethod
    def update_product(self, product_id, seller_id, data, expected_version):
        """Edita con bloqueo optimista (ProductConflict si cambió)."""

    @abstractmethod
    def can_delete(self, product, user):
        """True si `user` es el dueño o un administrador."""

    @abstractmethod
    def delete_product(self, product, user):
        """Borra (dueño o admin; ProductForbidden si no). Devuelve True si lo borró su dueño."""

    # ----------------------------------------------------------- moderación (admin)
    @abstractmethod
    def block_product(self, product_id, admin, reason):
        """Bloquea un producto activo y lo registra en admin_actions."""

    @abstractmethod
    def unblock_product(self, product_id, admin):
        """Desbloquea y lo registra en admin_actions."""

    @abstractmethod
    def delist_seller_products(self, seller_id):
        """Retira todos los productos de un vendedor dado de baja."""

    @abstractmethod
    def invalidate_cache(self):
        """Vacía la caché corta del catálogo (tras comprar, cancelar u opinar)."""
