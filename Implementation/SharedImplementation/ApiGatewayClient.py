"""Cliente HTTP del API Gateway (apiGatewayMarketplace). Lo usan todos los servicios que
guardan datos en DynamoDB: productos, carrito, favoritos, pedidos, ventas y reseñas.

Seguridad:
- La URL base viene solo de la configuración (nunca de la petición del usuario: sin SSRF).
- Toda llamada tiene timeout y no sigue redirecciones.
- El token del API viaja en una cabecera y jamás se registra ni se envía al navegador.
- El "actor" (rol, tienda y usuario) sale de la SESIÓN de Flask, nunca de un formulario.
"""
import logging

import requests

from Interfaces.ApiErrors import (
    ApiUnavailableError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)

logger = logging.getLogger("marketplace.security")


def actor_of(user):
    """(rol, seller_id, user_id) de la persona en sesión, para las cabeceras x-mkt-actor-*."""
    if user.is_admin:
        return ("admin", "", user.id)
    return ("user", user.seller_id or "", user.id)


class ApiGatewayClient:
    def __init__(self, base_url, token, timeout=(3.05, 10), session=None):
        if not base_url.startswith("https://"):
            raise ValueError("PRODUCTS_API_URL debe usar https://")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.session = session or requests.Session()

    def __repr__(self):  # nunca mostrar el token en logs o trazas
        return f"{type(self).__name__}({self.base_url!r})"

    def request(self, method, path, *, json=None, params=None, actor=None):
        headers = {"x-mkt-token": self._token, "Accept": "application/json"}
        if actor is not None:
            role, seller_id, *rest = actor
            headers["x-mkt-actor-role"] = role
            headers["x-mkt-actor-seller"] = seller_id or ""
            if rest and rest[0]:
                headers["x-mkt-actor-user"] = rest[0]
        try:
            response = self.session.request(
                method, self.base_url + path, json=json, params=params, headers=headers,
                timeout=self.timeout, allow_redirects=False,
            )
        except requests.RequestException as error:
            logger.error("event=products_api_unreachable error=%s", type(error).__name__)
            raise ApiUnavailableError("API no disponible") from error
        try:
            body = response.json() if response.content else {}
        except ValueError as error:
            raise ApiUnavailableError("Respuesta no JSON del API") from error
        if not isinstance(body, dict):
            raise ApiUnavailableError("Respuesta inesperada del API")
        status = response.status_code
        if 200 <= status < 300:
            return body
        message = str(body.get("mensaje") or body.get("message") or "")[:200]
        errors = [str(e)[:200] for e in body.get("errores", []) if isinstance(e, str)]
        if status == 404:
            raise NotFoundError(message)
        if status == 409:
            raise ConflictError(message, errors)
        if status == 400:
            raise ValidationFailedError(message, errors)
        if status == 403 and actor is not None and "Forbidden" != message:
            raise ForbiddenError(message)
        # 401/403 del autorizador = token mal configurado; 5xx = fallo del servicio.
        logger.error("event=products_api_error status=%s", status)
        raise ApiUnavailableError(f"API respondió {status}")

    _request = request  # nombre anterior (lo usan algunas pruebas)


def gateway():
    """El cliente único registrado en create_app() (las pruebas lo cambian por uno simulado)."""
    from flask import current_app

    return current_app.extensions["products_api"]
