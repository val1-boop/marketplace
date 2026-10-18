"""Archivos estáticos de cada vista (CSS, JS y fuentes).

Cada vista tiene sus carpetas CSS y JS (estructura del profesor). En lugar de publicar
toda la carpeta View —que también contiene código Python—, una sola ruta sirve
únicamente lo que pasa tres listas blancas: la vista, el tipo de carpeta y la extensión.
`send_from_directory` además impide salir de la carpeta (`../`).
"""
from pathlib import Path

from flask import abort, send_from_directory, url_for

from Core.Extensions import limiter

VIEW_ROOT = Path(__file__).resolve().parents[2]
VIEWS = {"SharedViews", "MainViews", "AuthViews", "ProductViews", "UserViews",
         "CartViews", "FavoriteViews", "OrderViews", "AddressViews", "ReviewViews"}
KINDS = {"CSS", "JS"}
# SVG solo como imagen (<img>/CSS): con nosniff y la CSP de la app no ejecuta scripts.
EXTENSIONS = {".css": "text/css", ".js": "text/javascript", ".ttf": "font/ttf", ".svg": "image/svg+xml"}


def register_assets(app):
    @app.route("/assets/<view>/<kind>/<path:filename>", endpoint="assets")
    @limiter.exempt
    def assets(view, kind, filename):
        suffix = Path(filename).suffix.lower()
        if view not in VIEWS or kind not in KINDS or suffix not in EXTENSIONS:
            abort(404)
        return send_from_directory(VIEW_ROOT / view / kind, filename, mimetype=EXTENSIONS[suffix],
                                   max_age=3600)


def asset_url(view, kind, filename):
    """URL de un archivo estático, p. ej. asset_url('ProductViews', 'CSS', 'Product.css')."""
    return url_for("assets", view=view, kind=kind, filename=filename)
