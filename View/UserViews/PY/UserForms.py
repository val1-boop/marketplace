"""Formularios de administración de usuarios (solo admin)."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Optional

from View.SharedViews.PY.SharedForms import (
    NoControlChars,
    SearchFormBase,
    email_field,
    name_field,
    new_password_field,
    strip_filter,
)

# Listas blancas: cualquier otro valor invalida el formulario.
ROLE_CHOICES = [("user", "Usuario"), ("admin", "Administrador")]
STATUS_CHOICES = [("active", "Activo"), ("suspended", "Suspendido"), ("banned", "Bloqueado")]


class AdminUserCreateForm(FlaskForm):
    first_name = name_field("Nombre", 60)
    last_name = name_field("Apellidos", 80)
    email = email_field()
    role = SelectField("Rol", choices=ROLE_CHOICES, default="user")
    password = new_password_field()
    confirm = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")],
        render_kw={"autocomplete": "new-password"},
    )


class AdminUserEditForm(FlaskForm):
    first_name = name_field("Nombre", 60)
    last_name = name_field("Apellidos", 80)
    email = email_field()
    role = SelectField("Rol", choices=ROLE_CHOICES)
    status = SelectField("Estado", choices=STATUS_CHOICES)
    status_reason = StringField(
        "Motivo del estado (opcional)",
        filters=[strip_filter],
        validators=[Optional(), Length(max=500), NoControlChars()],
    )
    new_password = new_password_field("Nueva contraseña (dejar vacío para no cambiarla)", optional=True)
    confirm = PasswordField(
        "Confirmar nueva contraseña",
        validators=[EqualTo("new_password", message="Las contraseñas no coinciden.")],
        render_kw={"autocomplete": "new-password"},
    )


class UserSearchForm(SearchFormBase):
    pass
