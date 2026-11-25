"""Contrato del servicio de tienda (perfil del vendedor)."""
from abc import ABC, abstractmethod


class ISellerService(ABC):
    @abstractmethod
    def get_store(self, user):
        """SellerDTO de la tienda de `user`, o None si todavía no la configuró."""

    @abstractmethod
    def save_store(self, user, data):
        """Crea o actualiza la tienda de `user` (SellerInputDTO). El seller_id sale de la cuenta."""
