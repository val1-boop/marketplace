"""ReviewService: publicar una reseña con estrellas (POST /items/<id>/reviews).

Solo quien recibió el producto y una sola vez (lo garantiza la Lambda con una transacción
condicional). El nombre público lo arma el servidor; el texto se muestra escapado (Jinja2)."""
from flask import Blueprint, abort, current_app, flash, redirect, url_for
from flask_login import current_user

from Core.Extensions import limiter
from Core.ServiceRegistry import review_service
from Interfaces.ApiErrors import ForbiddenError, NotFoundError, ValidationFailedError
from Security import role_required, security_log
from View.ReviewViews.PY.ReviewForms import ReviewForm

bp = Blueprint("reviews", __name__, url_prefix="/items")


@bp.route("/<product_id>/reviews", methods=["POST"])
@role_required("user")
@limiter.limit(lambda: current_app.config["REVIEW_RATE_LIMIT"])
def create(product_id):
    form = ReviewForm()
    target = url_for("items.detail", product_id=product_id) + "#opiniones"
    if not form.validate_on_submit():
        errors = [e for field in (form.rating, form.comment) for e in field.errors]
        flash(" ".join(errors) or "Revisa tu opinión.", "error")
        return redirect(target)
    try:
        review_service().create_review(current_user, product_id, form.rating.data, form.comment.data)
    except NotFoundError:
        abort(404)
    except ForbiddenError:
        security_log("review_denied", user=current_user.id, product=product_id)
        flash("Solo puedes opinar una vez sobre productos que compraste y recibiste.", "warning")
    except ValidationFailedError as error:
        flash("; ".join(error.errors) or str(error), "error")
    else:
        flash("¡Gracias por tu opinión!", "success")
    return redirect(target)
