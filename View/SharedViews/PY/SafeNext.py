"""Campo `next` (a dónde regresar después de una acción) sin open redirect."""
from flask import request, url_for

from Security import is_safe_redirect


def safe_next(default_endpoint, **values):
    """Ruta relativa del propio sitio tomada del formulario o de la URL; si no es segura,
    se usa la ruta por defecto. Nunca se redirige a otro dominio (`//evil.com`, `https:`)."""
    target = request.form.get("next") or request.args.get("next")
    if is_safe_redirect(target):
        return target
    return url_for(default_endpoint, **values)
