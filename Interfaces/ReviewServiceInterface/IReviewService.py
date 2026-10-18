"""Contrato de reseñas (DynamoDB Community + promedio en Products, por API Gateway).

Solo opina quien recibió el producto (pedido DELIVERED) y una sola vez; lo garantiza la
Lambda lambdaCreateReview con una transacción condicional."""
from abc import ABC, abstractmethod


class IReviewService(ABC):
    @abstractmethod
    def list_reviews(self, product_id, viewer):
        """ReviewListDTO: reseñas visibles y si `viewer` puede opinar."""

    @abstractmethod
    def create_review(self, user, product_id, rating, comment):
        """Publica la reseña con el nombre público "Nombre I." del usuario.
        ForbiddenError si no compró/recibió el producto o ya opinó."""
