"""SellerService: datos de la tienda del vendedor (rutas /store/...). Solo cuentas de usuario."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from Core.Extensions import limiter
from Core.ServiceRegistry import seller_service
from Security import role_required
from View.SellerViews.PY.SellerForms import StoreForm

bp = Blueprint("store", __name__, url_prefix="/store")


@bp.route("/edit", methods=["GET", "POST"])
@role_required("user")
@limiter.limit(lambda: current_app.config["ADDRESS_RATE_LIMIT"], methods=["POST"])
def edit():
    form = StoreForm(obj=seller_service().get_store(current_user))
    if request.method == "POST":  # ---- flujo POST: guardar
        if form.validate_on_submit():
            seller_service().save_store(current_user, form.to_dto())
            flash("Los datos de tu tienda se guardaron.", "success")
            return redirect(url_for("main.profile"))
    # ---- flujo GET (o POST con errores): mostrar el formulario
    return render_template("SellerViews/HTML/StoreForm.html", form=form)
