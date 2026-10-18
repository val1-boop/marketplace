"""Contrato de favoritos (DynamoDB Community: USER#<id> / FAV#<producto>, por API Gateway)."""
from abc import ABC, abstractmethod


class IFavoriteService(ABC):
    @abstractmethod
    def list_favorites(self, user):
        """Lista de FavoriteDTO (los productos que ya no están activos llegan sin producto)."""

    @abstractmethod
    def add_favorite(self, user, product_id):
        """Agrega (idempotente). ConflictError si llegó al máximo de 100."""

    @abstractmethod
    def remove_favorite(self, user, product_id):
        """Quita (idempotente)."""
