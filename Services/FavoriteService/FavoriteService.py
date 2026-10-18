"""FavoriteService: lista de favoritos (rutas /favorites/...). Solo cuentas de usuario.

Agregar y quitar son POST con CSRF; el regreso (`next`) solo acepta rutas del propio sitio."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, session
from flask_login import current_user

from Core.Extensions import limiter
from Core.ServiceRegistry import favorite_service
from Interfaces.ApiErrors import ConflictError, NotFoundError
from Security import role_required
from View.CartViews.PY.CartForms import AddToCartForm
from View.FavoriteViews.PY.FavoriteForms import FavoriteForm
from View.SharedViews.PY.SafeNext import safe_next

bp = Blueprint("favorites", __name__, url_prefix="/favorites")


def _limit():
    return current_app.config["CART_RATE_LIMIT"]


@bp.route("/")
@role_required("user")
def list_favorites():
    favorites = favorite_service().list_favorites(current_user)
    session["fav_ids"] = [f.product_id for f in favorites][:100]
    return render_template("FavoriteViews/HTML/Favorites.html", favorites=favorites,
                           fav_form=FavoriteForm(), cart_form=AddToCartForm())


@bp.route("/add/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def add(product_id):
    if not FavoriteForm().validate_on_submit():
        abort(400)
    try:
        favorite_service().add_favorite(current_user, product_id)
    except NotFoundError:
        abort(404)
    except ConflictError as error:
        flash(str(error) or "No se pudo agregar a favoritos.", "warning")
    else:
        ids = [i for i in session.get("fav_ids", []) if i != product_id]
        session["fav_ids"] = ([product_id] + ids)[:100]
        flash("Guardado en favoritos.", "success")
    return redirect(safe_next("items.detail", product_id=product_id))


@bp.route("/remove/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def remove(product_id):
    if not FavoriteForm().validate_on_submit():
        abort(400)
    try:
        favorite_service().remove_favorite(current_user, product_id)
    except NotFoundError:
        abort(404)
    session["fav_ids"] = [i for i in session.get("fav_ids", []) if i != product_id]
    flash("Quitado de favoritos.", "success")
    return redirect(safe_next("favorites.list_favorites"))
