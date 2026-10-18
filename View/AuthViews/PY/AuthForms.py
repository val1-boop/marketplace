"""Formularios de acceso: login, registro y cambio de contraseña."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length

from View.SharedViews.PY.SharedForms import (
    StrongPassword,
    email_field,
    name_field,
    new_password_field,
    strip_filter,
)


class LoginForm(FlaskForm):
    # En el login no se valida el formato del correo: cualquier error da el mismo mensaje.
    email = StringField(
        "Correo electrónico",
        filters=[strip_filter],
        validators=[DataRequired(), Length(max=254)],
        render_kw={"type": "email", "autocomplete": "username"},
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(max=128)],
        render_kw={"autocomplete": "current-password"},
    )


class RegisterForm(FlaskForm):
    first_name = name_field("Nombre", 60)
    last_name = name_field("Apellidos", 80)
    email = email_field()
    password = new_password_field()
    confirm = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")],
        render_kw={"autocomplete": "new-password"},
    )
    accept_terms = BooleanField(
        "Acepto los términos y el aviso de privacidad",
        validators=[DataRequired(message="Debes aceptar los términos.")],
    )


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Contraseña actual",
        validators=[DataRequired(), Length(max=128)],
        render_kw={"autocomplete": "current-password"},
    )
    new_password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=12, max=128), StrongPassword()],
        render_kw={"autocomplete": "new-password"},
    )
    confirm = PasswordField(
        "Confirmar nueva contraseña",
        validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden.")],
        render_kw={"autocomplete": "new-password"},
    )
