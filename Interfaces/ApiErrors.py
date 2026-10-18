"""Errores del API (API Gateway → Lambda), comunes a todos los servicios.

Las rutas los atrapan para responder con el código correcto (404, 403, 409…) y un
mensaje genérico; el detalle técnico nunca llega al navegador.
"""


class ApiUnavailableError(Exception):
    """El API no respondió o respondió algo inesperado (se muestra como 503 genérico)."""


class NotFoundError(Exception):
    """No existe, no es visible para quien lo pide o el ID no es válido (404)."""


class ForbiddenError(Exception):
    """El API rechazó la operación por dueño o rol (403)."""


class ConflictError(Exception):
    """El estado actual no permite la operación (409): existencias, versión, estado del pedido."""

    def __init__(self, message="", errors=None):
        super().__init__(message)
        self.errors = errors or []


class ValidationFailedError(Exception):
    """El API rechazó los datos (400); `errors` trae los motivos para mostrarlos."""

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []
