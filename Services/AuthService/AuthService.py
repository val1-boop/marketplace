"""AuthService: login, logout, registro y cambio de contraseña (rutas /auth/...)."""
import time

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from Core.Extensions import limiter
from Core.ServiceRegistry import auth_service
from Interfaces.AuthServiceInterface.AuthDTO import PasswordChangeDTO, RegistrationDTO
from Security import is_safe_redirect
from View.AuthViews.PY.AuthForms import ChangePasswordForm, LoginForm, RegisterForm

bp = Blueprint("auth", __name__, url_prefix="/auth")

GENERIC_LOGIN_ERROR = "Credenciales inválidas."
GENERIC_REGISTER_MSG = "Si los datos son válidos, la cuenta quedó registrada. Ya puedes iniciar sesión."


def _cfg_limit(key):
    return lambda: current_app.config[key]


def _start_session(user):
    # Regeneración de sesión: se descarta todo lo previo (anti session fixation).
    session.clear()
    login_user(user, remember=False)
    session.permanent = True
    session["auth_at"] = int(time.time())


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(_cfg_limit("LOGIN_RATE_LIMIT"), methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    next_url = request.args.get("next", "")
    if not is_safe_redirect(next_url):
        next_url = ""

    form = LoginForm()
    if form.validate_on_submit():
        user = auth_service().authenticate(form.email.data, form.password.data)
        if user is not None:
            _start_session(user)
            flash(f"Hola, {user.first_name}.", "success")
            return redirect(next_url or url_for("main.dashboard"))
        flash(GENERIC_LOGIN_ERROR, "error")
    elif request.method == "POST":
        flash(GENERIC_LOGIN_ERROR, "error")
    return render_template("AuthViews/HTML/Login.html", form=form, next_url=next_url)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    auth_service().logout(current_user._get_current_object())
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit(_cfg_limit("REGISTER_RATE_LIMIT"), methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        # Solo se usan los campos declarados; role, status y seller_id los define el servidor.
        auth_service().register(RegistrationDTO(
            first_name=form.first_name.data, last_name=form.last_name.data,
            email=form.email.data, password=form.password.data,
        ))
        flash(GENERIC_REGISTER_MSG, "success")
        return redirect(url_for("auth.login"))
    return render_template("AuthViews/HTML/Register.html", form=form)


@bp.route("/password", methods=["GET", "POST"])
@login_required
@limiter.limit(_cfg_limit("CREDENTIAL_CHANGE_RATE_LIMIT"), methods=["POST"])
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        result = auth_service().change_password(
            current_user._get_current_object(),
            PasswordChangeDTO(form.current_password.data, form.new_password.data),
        )
        if result.ok:
            logout_user()
            session.clear()
            flash("Contraseña actualizada. Inicia sesión con la nueva contraseña.", "success")
            return redirect(url_for("auth.login"))
        getattr(form, result.field).errors.append(result.message)
    return render_template("AuthViews/HTML/ChangePassword.html", form=form)
