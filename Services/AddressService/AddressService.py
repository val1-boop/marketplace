"""AddressService: direcciones de envío (rutas /addresses/...). Solo cuentas de usuario.

El ID de la dirección va en la URL como entero, pero el servicio SIEMPRE filtra por el
usuario de la sesión: la dirección de otra persona responde 404 (anti IDOR)."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from Core.Extensions import limiter
from Core.ServiceRegistry import address_service
from Interfaces.AddressServiceInterface.AddressDTO import AddressLimitError
from Security import role_required, security_log
from View.AddressViews.PY.AddressForms import AddressForm
from View.SharedViews.PY.SafeNext import safe_next
from View.SharedViews.PY.SharedForms import ConfirmForm

bp = Blueprint("addresses", __name__, url_prefix="/addresses")


def _limit():
    return current_app.config["ADDRESS_RATE_LIMIT"]


def _not_mine(address_id, op):
    security_log("idor_blocked", user=current_user.id, address=address_id, op=op)
    abort(404)


@bp.route("/")
@role_required("user")
def list_addresses():
    return render_template("AddressViews/HTML/Addresses.html",
                           addresses=address_service().list_addresses(current_user), confirm_form=ConfirmForm())


@bp.route("/new", methods=["GET", "POST"])
@role_required("user")
@limiter.limit(_limit, methods=["POST"])
def create():
    form = AddressForm()
    if request.method == "GET":
        form.next.data = request.args.get("next", "")
    if form.validate_on_submit():
        try:
            address_service().create_address(current_user, form.to_dto())
        except AddressLimitError as error:
            flash(str(error), "warning")
        else:
            flash("Dirección guardada.", "success")
            return redirect(safe_next("addresses.list_addresses"))
    return render_template("AddressViews/HTML/AddressForm.html", form=form, address=None)


@bp.route("/<int:address_id>/edit", methods=["GET", "POST"])
@role_required("user")
@limiter.limit(_limit, methods=["POST"])
def edit(address_id):
    address = address_service().get_address(current_user, address_id)
    if address is None:
        _not_mine(address_id, "edit")
    form = AddressForm(obj=address)
    if request.method == "GET":
        form.make_default.data = address.is_default
    if form.validate_on_submit():
        address_service().update_address(current_user, address_id, form.to_dto())
        flash("Dirección actualizada. Los pedidos ya hechos conservan la dirección original.", "success")
        return redirect(url_for("addresses.list_addresses"))
    return render_template("AddressViews/HTML/AddressForm.html", form=form, address=address)


@bp.route("/<int:address_id>/default", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def make_default(address_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    if not address_service().set_default(current_user, address_id):
        _not_mine(address_id, "default")
    flash("Dirección predeterminada actualizada.", "success")
    return redirect(url_for("addresses.list_addresses"))


@bp.route("/<int:address_id>/delete", methods=["POST"])
@role_required("user")
@limiter.limit(_limit)
def delete(address_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    if not address_service().deactivate_address(current_user, address_id):
        _not_mine(address_id, "delete")
    flash("Dirección eliminada.", "success")
    return redirect(url_for("addresses.list_addresses"))
