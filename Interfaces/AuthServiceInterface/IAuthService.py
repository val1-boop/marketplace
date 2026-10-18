"""Contrato del servicio de autenticación (login, registro, logout, contraseña)."""
from abc import ABC, abstractmethod


class IAuthService(ABC):
    @abstractmethod
    def authenticate(self, email, password):
        """Devuelve el User si las credenciales son válidas y la cuenta no está bloqueada;
        None en cualquier otro caso (sin decir por qué: anti enumeración)."""

    @abstractmethod
    def register(self, data):
        """RegistrationDTO → True si se creó; False si el correo ya existía (sin revelarlo)."""

    @abstractmethod
    def logout(self, user):
        """Rota el session_nonce (invalida la cookie en el servidor) y registra el evento."""

    @abstractmethod
    def change_password(self, user, data):
        """PasswordChangeDTO → PasswordChangeResult. Si cambia, cierra todas las sesiones."""
