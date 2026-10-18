"""Contrato del servicio de usuarios (solo administradores)."""
from abc import ABC, abstractmethod


class IUserService(ABC):
    @abstractmethod
    def search_users(self, q, page, per_page):
        """Paginación de usuarios no eliminados; `q` busca literal en correo y nombre."""

    @abstractmethod
    def empty_search(self, page, per_page):
        """Paginación vacía (búsqueda inválida: no se devuelve nada)."""

    @abstractmethod
    def get_user(self, user_id):
        """El usuario, o None si no existe o fue eliminado."""

    @abstractmethod
    def user_products(self, user):
        """Últimos productos de su tienda (para la ficha del usuario)."""

    @abstractmethod
    def create_user(self, admin, data):
        """UserCreateDTO → UserResult."""

    @abstractmethod
    def update_user(self, admin, user, data):
        """UserUpdateDTO → UserResult. Aplica las reglas: nadie cambia su propio rol o estado
        y siempre queda al menos un administrador activo."""

    @abstractmethod
    def delete_user(self, admin, user):
        """Borrado lógico. Devuelve un mensaje de error o "" si se eliminó."""
