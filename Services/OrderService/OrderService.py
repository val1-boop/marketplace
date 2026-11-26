"""OrderService: comprar, "Mis compras", detalle con estados y "Mis ventas".

Rutas: /checkout, /orders/, /orders/<id>, /orders/<id>/status, /sales/

Seguridad:
- Comprar y cambiar estados son POST con CSRF y límite de peticiones.
- La dirección elegida debe ser del usuario (RadioField con SUS direcciones + filtro por
  user_id en el servicio). Precios y existencias los decide la Lambda, no el navegador.
- Ver un pedido ajeno responde 404 (la Lambda no confirma que existe).
- Quién puede avanzar o cancelar lo decide la Lambda (comprador, vendedor o admin).
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from Core.Extensions import limiter
from Core.ServiceRegistry import address_service, cart_service, order_service
from Interfaces.ApiErrors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from Security import role_required, security_log
from View.OrderViews.PY.OrderForms import CheckoutForm, OrderActionForm

bp = Blueprint("orders", __name__)

DONE_MESSAGES = {
    "prepare": "Pedido marcado en preparación.",
    "ship": "Pedido marcado como enviado.",
    "deliver": "¡Listo! Confirmaste que recibiste tu pedido. Ya puedes opinar sobre el producto.",
    "cancel": "Pedido cancelado. Las piezas regresaron al inventario.",
}


@bp.route("/checkout", methods=["GET", "POST"])
@role_required("user")
@limiter.limit(lambda: current_app.config["CHECKOUT_RATE_LIMIT"], methods=["POST"])
def checkout():
    cart = cart_service().get_cart(current_user)
    if not cart.lines:
        flash("Tu carrito está vacío.", "info")
        return redirect(url_for("cart.view"))
    addresses = address_service().list_addresses(current_user)
    if not addresses:
        # Sin dirección no se puede pagar: se lleva a crearla y se regresa aquí.
        flash("Agrega una dirección de envío para continuar con tu compra.", "info")
        return redirect(url_for("addresses.create", next=url_for("orders.checkout")))
    form = CheckoutForm()
    form.set_addresses(addresses)

    if request.method == "POST":  # ---- flujo POST: pagar
        return _pay(cart, addresses, form)
    # ---- flujo GET: solo muestra el resumen y el formulario
    return render_template("OrderViews/HTML/Checkout.html", cart=cart, addresses=addresses, form=form)


def _pay(cart, addresses, form):
    """Flujo POST del checkout: valida el formulario y crea los pedidos."""
    if not form.validate_on_submit():
        flash("Revisa la dirección de envío elegida.", "error")
        return render_template("OrderViews/HTML/Checkout.html", cart=cart, addresses=addresses, form=form), 400
    try:
        orders = order_service().checkout(current_user, form.address_id.data)
    except NotFoundError:
        abort(404)
    except (ConflictError, ValidationFailedError) as error:
        flash(str(error) + (": " + "; ".join(error.errors) if error.errors else ""), "warning")
        return redirect(url_for("cart.view"))
    session["cart_count"] = 0
    security_log("order_created", user=current_user.id, orders=len(orders))
    if len(orders) == 1:
        flash("¡Pago exitoso! Tu pedido quedó confirmado y aquí te avisamos cada cambio de estado.", "success")
        return redirect(url_for("orders.detail", order_id=orders[0].order_id))
    flash(f"¡Pago exitoso! Se crearon {len(orders)} pedidos, uno por cada vendedor.", "success")
    return redirect(url_for("orders.list_orders"))


@bp.route("/orders/")
@role_required("user")
def list_orders():
    return render_template("OrderViews/HTML/Orders.html", orders=order_service().list_orders(current_user),
                           mode="buyer")


@bp.route("/sales/")
@role_required("user")
def list_sales():
    return render_template("OrderViews/HTML/Orders.html", orders=order_service().list_sales(current_user),
                           mode="seller")


@bp.route("/orders/<order_id>")
@login_required
def detail(order_id):
    try:
        order = order_service().get_order(current_user, order_id)
    except NotFoundError:
        abort(404)
    return render_template("OrderViews/HTML/OrderDetail.html", order=order, action_form=OrderActionForm())


@bp.route("/orders/<order_id>/status", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["ORDER_STATUS_RATE_LIMIT"])
def change_status(order_id):
    form = OrderActionForm()
    if not form.validate_on_submit():
        abort(400)
    action = form.action.data
    try:
        order_service().change_status(current_user, order_id, action, form.reason.data or "")
    except NotFoundError:
        abort(404)
    except ForbiddenError:
        security_log("order_action_denied", user=current_user.id, order=order_id, action=action)
        abort(403)
    except ConflictError as error:
        flash(str(error) or "El pedido cambió mientras tanto.", "warning")
    except ValidationFailedError as error:
        flash("; ".join(error.errors) or str(error), "error")
    else:
        flash(DONE_MESSAGES[action], "success")
    return redirect(url_for("orders.detail", order_id=order_id))
