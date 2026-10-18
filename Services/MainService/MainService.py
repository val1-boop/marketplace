"""MainService: la página principal del marketplace (Main Home Page), el panel de
administración y el perfil.

- "/"          portada PÚBLICA: cualquiera puede ver departamentos y productos.
- "/dashboard" inicio personal (con sesión): saludo y resumen de tu tienda; para un
               administrador es el panel de administración.
"""
from flask import Blueprint, render_template
from flask_login import current_user, login_required

from Core.ServiceRegistry import main_service

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    home = main_service().home(current_user)
    return render_template("MainViews/HTML/Home.html", **vars(home))


@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        panel = main_service().admin_dashboard()
        return render_template("MainViews/HTML/AdminDashboard.html", **vars(panel))
    home = main_service().home(current_user)
    return render_template("MainViews/HTML/Home.html", **vars(home))


@bp.route("/profile")
@login_required
def profile():
    return render_template("MainViews/HTML/Profile.html", user=current_user)
