"""Contrato de pedidos y ventas (DynamoDB Orders, por API Gateway).

Un pago real queda fuera del alcance (pendiente de confirmar con el profesor): al confirmar
la compra el pedido nace en estado CONFIRMED."""
from abc import ABC, abstractmethod


class IOrderService(ABC):
    @abstractmethod
    def checkout(self, user, address_id):
        """Convierte el carrito en pedidos (uno por vendedor) enviando una COPIA de la
        dirección elegida. Devuelve la lista de OrderSummaryDTO creados.
        NotFoundError si la dirección no es del usuario; ConflictError si el carrito cambió."""

    @abstractmethod
    def list_orders(self, user):
        """"Mis compras": lista de OrderSummaryDTO, el más reciente primero."""

    @abstractmethod
    def list_sales(self, user):
        """"Mis ventas": pedidos que recibió su tienda."""

    @abstractmethod
    def get_order(self, user, order_id):
        """OrderDetailDTO si es comprador, vendedor o admin; NotFoundError en otro caso."""

    @abstractmethod
    def change_status(self, user, order_id, action, reason=""):
        """prepare | ship | deliver | cancel. ForbiddenError / ConflictError según el caso."""
