"""Contrato del carrito (DynamoDB Marketplace: USER#<id> / CART#<producto>, por API Gateway).

El precio y las existencias SIEMPRE se leen de Products al mostrar y al comprar; el
navegador solo manda el ID del producto y la cantidad."""
from abc import ABC, abstractmethod


class ICartService(ABC):
    @abstractmethod
    def get_cart(self, user):
        """CartDTO con precios actuales y avisos por renglón."""

    @abstractmethod
    def add_item(self, user, product_id, quantity):
        """Suma unidades (máximo 10 por producto). ConflictError si no hay existencias,
        es su propio producto o el carrito ya tiene 10 productos distintos."""

    @abstractmethod
    def set_quantity(self, user, product_id, quantity):
        """Fija la cantidad de un renglón."""

    @abstractmethod
    def remove_item(self, user, product_id):
        """Quita el renglón (si no existe, no pasa nada)."""

    @abstractmethod
    def refresh_counters(self, user, session):
        """Guarda en la sesión el número de piezas del carrito y los IDs favoritos
        (solo para pintar el contador y los corazones; no se usan para autorizar)."""
