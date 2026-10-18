"""Errores del servicio de productos: son los errores comunes del API con nombres de
producto, para que el código de productos se lea claro (ver Interfaces/ApiErrors.py)."""
from Interfaces.ApiErrors import (
    ApiUnavailableError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)

ProductsAPIError = ApiUnavailableError
ProductNotFound = NotFoundError
ProductForbidden = ForbiddenError
ProductConflict = ConflictError
ProductValidationError = ValidationFailedError

__all__ = ["ProductsAPIError", "ProductNotFound", "ProductForbidden", "ProductConflict",
           "ProductValidationError"]
