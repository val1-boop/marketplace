"""Lambda lambdaAuthorizer: autorizador del API HTTP (payload 2.0, respuesta simple).

Solo deja pasar peticiones que traen la cabecera x-mkt-token con el secreto que conoce
el servidor Flask. Así, aunque alguien vea la URL del API, no puede crear, modificar ni
borrar productos sin pasar por el login y los controles de la aplicación.

Python 3.14, rol LabRole, variable de entorno API_TOKEN (la misma que PRODUCTS_API_TOKEN
en el .env de Flask, mínimo 32 caracteres), timeout 5 s.
"""
import hmac
import os

EXPECTED = os.environ.get("API_TOKEN", "")


def lambda_handler(event, context):
    headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    received = headers.get("x-mkt-token", "")
    # Si la variable no está configurada (o es débil) se niega todo: falla cerrado.
    authorized = len(EXPECTED) >= 32 and hmac.compare_digest(
        received.encode("utf-8"), EXPECTED.encode("utf-8")
    )
    return {"isAuthorized": authorized}
