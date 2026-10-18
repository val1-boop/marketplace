"""ProductService: catálogo y productos (rutas /items/...).

PÚBLICAS (sin cuenta, como Mercado Libre): catálogo, búsqueda, filtros y ficha.
CON SESIÓN: publicar, editar, borrar y "Mis productos" (rol user = comprador y vendedor).
SOLO ADMIN: bloquear y desbloquear.

Cada ruta revisa permisos en el servidor; ocultar un botón no protege nada.
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from Core.Catalog import SORTS
from Core.Extensions import limiter
from Core.ServiceRegistry import product_service, review_service
from Interfaces.ApiErrors import ApiUnavailableError
from Interfaces.ProductServiceInterface.ProductDTO import CatalogQueryDTO
from Interfaces.ProductServiceInterface.ProductErrors import (
    ProductConflict,
    ProductForbidden,
    ProductNotFound,
    ProductValidationError,
)
from Security import role_required, security_log
from View.CartViews.PY.CartForms import AddToCartForm
from View.ProductViews.PY.ProductForms import MyProductsSearchForm, ProductForm, ProductSearchForm, ReasonForm
from View.ProductViews.Utils.CatalogFilters import active_chips, make_filter_url
from View.SharedViews.PY.SharedForms import ConfirmForm
from View.ReviewViews.PY.ReviewForms import ReviewForm
from View.SharedViews.Utils.Pagination import ListPagination, get_page

bp = Blueprint("items", __name__, url_prefix="/items")
PER_PAGE = 18
RECOMMENDED = 8


def _product_or_404(product_id):
    try:
        return product_service().get_product(product_id, current_user)
    except ProductNotFound:
        abort(404)


def _show_api_validation(error):
    security_log("products_api_rejected", user=current_user.id)
    flash("El servicio rechazó los datos: " + "; ".join(error.errors or [str(error)]), "error")


# ---------------------------------------------------------------- públicas
@bp.route("/")
@limiter.limit(lambda: current_app.config["SEARCH_RATE_LIMIT"])
def catalog():
    form = ProductSearchForm(formdata=request.args)
    valid = form.validate()
    query = form.to_dto() if valid else CatalogQueryDTO()  # búsqueda inválida: sin resultados
    result = product_service().search_catalog(query) if valid else None
    products = result.products if result else []
    facets = result.facets if result else {"department": {}, "category": {}, "availability": {}}
    pagination = ListPagination(products, get_page(request.args), PER_PAGE)
    filter_url = make_filter_url(query)
    # "Te recomendamos": los mejor calificados (de la misma caché del catálogo).
    # Solo sin búsqueda ni filtros: con filtros, la página muestra únicamente lo que coincide.
    shown = {p.product_id for p in pagination.items}
    filtered = not valid or any((query.q, query.department, query.category, query.availability))
    recommended = [] if filtered else sorted((p for p in product_service().list_active_products() if p.product_id not in shown),
                         key=lambda p: (p.rating_avg, p.rating_count, p.sales_count), reverse=True)[:RECOMMENDED]
    return render_template(
        "ProductViews/HTML/Catalog.html", form=form, valid=valid, pagination=pagination,
        params=query.__dict__, facets=facets, chips=active_chips(query, filter_url),
        filter_url=filter_url, sorts=SORTS, recommended=recommended,
        seller_names=product_service().seller_names(p.seller_id for p in pagination.items),
        recommended_names=product_service().seller_names(p.seller_id for p in recommended),
    )


@bp.route("/<product_id>")
def detail(product_id):
    try:
        detail_dto = product_service().get_product_detail(product_id, current_user)
    except ProductNotFound:
        abort(404)
    # Las opiniones son un extra: si el servicio no responde, la ficha se muestra igual.
    try:
        reviews = review_service().list_reviews(product_id, current_user)
    except ApiUnavailableError:
        reviews = None
    return render_template("ProductViews/HTML/ProductDetail.html", **vars(detail_dto),
                           confirm_form=ConfirmForm(), cart_form=AddToCartForm(), reviews=reviews,
                           review_form=ReviewForm() if reviews and reviews.can_review else None)


# ---------------------------------------------------------------- vendedor (con sesión)
@bp.route("/mine")
@role_required("user")
def mine():
    form = MyProductsSearchForm(formdata=request.args)
    valid = form.validate()  # búsqueda inválida: se ignoran los filtros y se muestran todos
    q = (form.q.data or "") if valid else ""
    category = (form.category.data or "") if valid else ""
    status = (form.status.data or "") if valid else ""
    products = product_service().search_seller_products(current_user.seller_id, q, category, status)
    pagination = ListPagination(products, get_page(request.args), PER_PAGE)
    return render_template(
        "ProductViews/HTML/MyProducts.html", pagination=pagination, form=form, valid=valid,
        confirm_form=ConfirmForm(), params={"q": q, "category": category, "status": status},
    )


@bp.route("/new", methods=["GET", "POST"])
@role_required("user")
def create():
    if not current_user.seller_id:
        abort(403)
    form = ProductForm()
    if form.validate_on_submit():
        try:
            # El seller_id sale de la sesión; el product_id lo genera la Lambda.
            product = product_service().create_product(current_user.seller_id, form.to_dto())
        except ProductValidationError as error:
            _show_api_validation(error)
        else:
            flash("Producto publicado.", "success")
            return redirect(url_for("items.detail", product_id=product.product_id))
    return render_template("ProductViews/HTML/ProductForm.html", form=form, product=None)


@bp.route("/<product_id>/edit", methods=["GET", "POST"])
@role_required("user")
def edit(product_id):
    try:
        product = product_service().get_owned_product(product_id, current_user)  # anti IDOR
    except ProductNotFound:
        abort(404)
    except ProductForbidden:
        abort(403)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        try:
            product_service().update_product(
                product_id, current_user.seller_id, form.to_dto(), form.version.data or 0
            )
        except ProductConflict:
            flash("El producto cambió mientras lo editabas. Revisa los datos y vuelve a guardar.", "warning")
            return redirect(url_for("items.edit", product_id=product_id))
        except ProductForbidden:
            security_log("idor_blocked", user=current_user.id, product=product_id, op="edit-api")
            abort(403)
        except ProductNotFound:
            abort(404)
        except ProductValidationError as error:
            _show_api_validation(error)
        else:
            flash("Cambios guardados.", "success")
            return redirect(url_for("items.detail", product_id=product_id))
    return render_template("ProductViews/HTML/ProductForm.html", form=form, product=product)


@bp.route("/<product_id>/delete", methods=["POST"])
@login_required
def delete(product_id):
    product = _product_or_404(product_id)
    if not product_service().can_delete(product, current_user):
        security_log("idor_blocked", user=current_user.id, product=product_id, op="delete")
        abort(403)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    try:
        owner = product_service().delete_product(product, current_user)
    except ProductForbidden:
        abort(403)
    except ProductNotFound:
        abort(404)
    flash(f"Producto {product_id} eliminado.", "success")
    return redirect(url_for("items.mine" if owner else "items.catalog"))


# ---------------------------------------------------------------- moderación (admin)
@bp.route("/<product_id>/block", methods=["GET", "POST"])
@role_required("admin", "super_admin")
def block(product_id):
    product = _product_or_404(product_id)
    if product.status != "ACTIVE":
        flash("Solo se pueden bloquear productos activos.", "warning")
        return redirect(url_for("items.detail", product_id=product_id))
    form = ReasonForm()
    if form.validate_on_submit():
        try:
            product_service().block_product(product_id, current_user, form.reason.data)
        except ProductConflict:
            flash("El producto ya no está activo.", "warning")
        except ProductValidationError as error:
            _show_api_validation(error)
            return render_template("ProductViews/HTML/BlockProduct.html", form=form, product=product)
        else:
            flash("Producto bloqueado.", "success")
        return redirect(url_for("items.detail", product_id=product_id))
    return render_template("ProductViews/HTML/BlockProduct.html", form=form, product=product)


@bp.route("/<product_id>/unblock", methods=["POST"])
@role_required("admin", "super_admin")
def unblock(product_id):
    _product_or_404(product_id)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    try:
        product_service().unblock_product(product_id, current_user)
    except ProductConflict:
        flash("El producto no está bloqueado.", "warning")
    else:
        flash("Producto desbloqueado.", "success")
    return redirect(url_for("items.detail", product_id=product_id))
