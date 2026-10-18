"""Contrato del servicio de direcciones (RDS MySQL, tabla addresses).

Toda operación recibe al usuario de la sesión y filtra por su user_id: una dirección
ajena se comporta igual que una que no existe (anti IDOR)."""
from abc import ABC, abstractmethod


class IAddressService(ABC):
    @abstractmethod
    def list_addresses(self, user):
        """Direcciones activas del usuario (la predeterminada primero) como AddressDTO."""

    @abstractmethod
    def get_address(self, user, address_id):
        """AddressDTO del usuario, o None si no existe, está inactiva o es de otra persona."""

    @abstractmethod
    def create_address(self, user, data):
        """AddressInputDTO → AddressDTO. AddressLimitError si ya tiene el máximo."""

    @abstractmethod
    def update_address(self, user, address_id, data):
        """Actualiza; None si no es suya."""

    @abstractmethod
    def set_default(self, user, address_id):
        """La marca como predeterminada (y desmarca la anterior). False si no es suya."""

    @abstractmethod
    def deactivate_address(self, user, address_id):
        """Baja lógica (is_active = FALSE). False si no es suya."""

    @abstractmethod
    def shipping_copy(self, user, address_id):
        """Diccionario de envío para el pedido, o None si no es suya."""
