"""Campo `next` (a dónde regresar después de una acción) sin open redirect."""
from urllib.parse import urlsplit

from flask import request, url_for

from Security import is_safe_redirect


def safe_next(default_endpoint, **values):
    """Ruta relativa del propio sitio tomada del formulario o de la URL; si no es segura,
    se usa la ruta por defecto. Nunca se redirige a otro dominio (`//evil.com`, `https:`)."""
    target = request.form.get("next") or request.args.get("next")
    if is_safe_redirect(target):
        return target
    return url_for(default_endpoint, **values)


def origin_page():
    """Ruta de la página del propio sitio desde la que se hizo la petición (cabecera Referer),
    o None. Sirve para volver a la ficha del producto después de iniciar sesión.

    El Referer lo controla el cliente, así que se trata como entrada no confiable: debe ser del
    mismo host que la petición (no sirve `evil.com`, `localhost.evil.com` ni `localhost@evil.com`),
    no puede ser una pantalla de acceso (evita bucles) y el resultado pasa por is_safe_redirect.
    """
    try:
        parts = urlsplit(request.referrer or "")
    except ValueError:
        return None
    if not parts.netloc or parts.netloc != request.host or parts.path.startswith("/auth/"):
        return None
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    return target if is_safe_redirect(target) else None
