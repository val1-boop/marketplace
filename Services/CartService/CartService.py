"""CartService: carrito de compras (rutas /cart/...). Solo cuentas de usuario (no admin).

Seguridad:
- POST + CSRF en toda acción que cambia el carrito; límite de peticiones por minuto.
- El producto viene en la URL y se valida con lista blanca; el precio nunca viene del navegador.
- La Lambda vuelve a validar existencias, estado y que no compres tu propio producto.
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user

from Core.Extensions import limiter
from Core.ServiceRegistry import cart_service
from Interfaces.ApiErrors import ConflictError, NotFoundError, ValidationFailedError
from Security import role_required
from View.CartViews.PY.CartForms import AddToCartForm, UpdateQuantityForm
from View.SharedViews.PY.SafeNext import safe_next
from View.SharedViews.PY.SharedForms import ConfirmForm

bp = Blueprint("cart", __name__, url_prefix="/cart")


def _limit():
    return current_app.config["CART_RATE_LIMIT"]


def _refresh_count():
    cart_service().refresh_counters(current_user, session)


def _add(product_id):
    form = AddToCartForm()
    if not form.validate_on_submit():
        flash("Cantidad no válida (de 1 a 10).", "error")
        return False
    try:
        cart_service().add_item(current_user, product_id, form.quantity.data)
    except NotFoundError:
        abort(404)
    except (ConflictError, ValidationFailedError) as error:
        flash(str(error) or "No se pudo agregar al carrito.", "warning")
        return False
    _refresh_count()
    return True


@bp.route("/")
@role_required("user")
def view():
    cart = cart_service().get_cart(current_user)
    session["cart_count"] = cart.units
    return render_template("CartViews/HTML/Cart.html", cart=cart, qty_form=UpdateQuantityForm(),
                           confirm_form=ConfirmForm())


@bp.route("/add/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def add(product_id):
    if _add(product_id):
        flash("Producto agregado a tu carrito.", "success")
    return redirect(safe_next("items.detail", product_id=product_id))


@bp.route("/buy/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def buy_now(product_id):
    """"Comprar ahora": lo agrega al carrito y lleva directo a confirmar la compra."""
    if _add(product_id):
        return redirect(url_for("orders.checkout"))
    return redirect(url_for("items.detail", product_id=product_id))


@bp.route("/update/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def update(product_id):
    form = UpdateQuantityForm()
    if not form.validate_on_submit():
        flash("Cantidad no válida (de 1 a 10).", "error")
        return redirect(url_for("cart.view"))
    try:
        cart_service().set_quantity(current_user, product_id, form.quantity.data)
    except NotFoundError:
        flash("Ese producto ya no está disponible; quítalo del carrito.", "warning")
    except (ConflictError, ValidationFailedError) as error:
        flash(str(error) or "No se pudo actualizar la cantidad.", "warning")
    else:
        flash("Cantidad actualizada.", "success")
    return redirect(url_for("cart.view"))


@bp.route("/remove/<product_id>", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def remove(product_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    try:
        cart_service().remove_item(current_user, product_id)
    except NotFoundError:
        abort(404)
    flash("Producto quitado del carrito.", "success")
    return redirect(url_for("cart.view"))
