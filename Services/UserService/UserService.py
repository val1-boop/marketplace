"""UserService: CRUD de usuarios, exclusivo para administradores (rutas /users/...)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from Core.ServiceRegistry import user_service
from Interfaces.UserServiceInterface.UserDTO import UserCreateDTO, UserUpdateDTO
from Security import security_log
from View.SharedViews.PY.SharedForms import ConfirmForm
from View.SharedViews.Utils.Pagination import get_page
from View.UserViews.PY.UserForms import AdminUserCreateForm, AdminUserEditForm, UserSearchForm

bp = Blueprint("users", __name__, url_prefix="/users")
PER_PAGE = 20


@bp.before_request
@login_required
def require_admin():
    # Defensa en profundidad: TODO el blueprint exige rol admin, aunque se agregue una ruta
    # nueva y se olvide su decorador, o se escriba la URL a mano.
    if not current_user.is_admin:
        security_log("access_denied", user=current_user.id, area="users")
        abort(403)
    return None


def _user_or_404(user_id):
    user = user_service().get_user(user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/")
def list_users():
    form = UserSearchForm(formdata=request.args)
    page = get_page(request.args)
    if form.validate():
        q = form.q.data or ""
        pagination = user_service().search_users(q, page, PER_PAGE)
    else:
        q = ""
        pagination = user_service().empty_search(page, PER_PAGE)
    return render_template("UserViews/HTML/UserList.html", form=form, pagination=pagination, q=q)


@bp.route("/new", methods=["GET", "POST"])
def create():
    form = AdminUserCreateForm()
    if form.validate_on_submit():
        result = user_service().create_user(current_user, UserCreateDTO(
            first_name=form.first_name.data, last_name=form.last_name.data,
            email=form.email.data, role=form.role.data, password=form.password.data,
        ))
        if result.user is not None:
            flash("Usuario creado.", "success")
            return redirect(url_for("users.detail", user_id=result.user.id))
        form.email.errors.append(result.error)
    return render_template("UserViews/HTML/UserForm.html", form=form, user=None)


@bp.route("/<uuid:user_id>")
def detail(user_id):
    user = _user_or_404(user_id)
    return render_template("UserViews/HTML/UserDetail.html", user=user,
                           products=user_service().user_products(user), confirm_form=ConfirmForm())


@bp.route("/<uuid:user_id>/edit", methods=["GET", "POST"])
def edit(user_id):
    user = _user_or_404(user_id)
    form = AdminUserEditForm(obj=user)
    if form.validate_on_submit():
        result = user_service().update_user(current_user, user, UserUpdateDTO(
            first_name=form.first_name.data, last_name=form.last_name.data, email=form.email.data,
            role=form.role.data, status=form.status.data,
            status_reason=form.status_reason.data or "", new_password=form.new_password.data or "",
        ))
        if result.user is None:
            if result.field == "email":
                form.email.errors.append("Ese correo ya está registrado.")
            flash(result.error, "error")
            return render_template("UserViews/HTML/UserForm.html", form=form, user=user), 400
        flash("Usuario actualizado.", "success")
        return redirect(url_for("users.detail", user_id=user.id))
    return render_template("UserViews/HTML/UserForm.html", form=form, user=user)


@bp.route("/<uuid:user_id>/delete", methods=["POST"])
def delete(user_id):
    user = _user_or_404(user_id)
    if not ConfirmForm().validate_on_submit():
        abort(400)
    error = user_service().delete_user(current_user, user)
    if error:
        flash(error, "error")
        return redirect(url_for("users.detail", user_id=user.id))
    flash("Usuario eliminado.", "success")
    return redirect(url_for("users.list_users"))
