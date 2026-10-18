"""Piezas de formulario compartidas (WTForms). El servidor es la fuente de verdad de la
validación: los atributos HTML (required, maxlength…) solo ayudan al usuario.

Solo los campos declarados en un formulario se leen de la petición; cualquier campo
extra (role=admin, seller_id, status…) se ignora (anti mass assignment).
"""
import unicodedata

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, ValidationError

from Security import check_password_policy, normalize_text

NAME_RE = r"^[^\W\d_]+(?:[ '.\-][^\W\d_]+)*$"
NAME_MSG = "Solo letras, espacios, apóstrofo, punto o guion."
SEARCH_MAX = 64


def strip_filter(value):
    return normalize_text(value)


class NoControlChars:
    """Rechaza caracteres de control/formato Unicode (CRLF, NUL, zero-width, etc.).
    Con allow_newlines=True (textos largos) se permite solo el salto de línea \\n."""

    def __init__(self, allow_newlines=False):
        self.allow_newlines = allow_newlines

    def __call__(self, form, field):
        if not field.data:
            return
        text = str(field.data)
        if self.allow_newlines:
            text = text.replace("\r\n", "\n").replace("\n", "")
        if any(unicodedata.category(c).startswith("C") for c in text):
            raise ValidationError("Contiene caracteres no permitidos.")


class StrongPassword:
    """Aplica la política de contraseñas (Security.check_password_policy)."""

    def __init__(self, email_field=None):
        self.email_field = email_field

    def __call__(self, form, field):
        email = getattr(form, self.email_field).data if self.email_field else None
        errors = check_password_policy(field.data or "", email)
        if errors:
            raise ValidationError(" ".join(errors))


def name_field(label, max_len):
    return StringField(
        label,
        filters=[strip_filter],
        validators=[DataRequired(), Length(min=1, max=max_len), NoControlChars(), Regexp(NAME_RE, message=NAME_MSG)],
    )


def email_field():
    return StringField(
        "Correo electrónico",
        filters=[strip_filter],
        validators=[DataRequired(), Length(max=254), NoControlChars(), Email(message="Correo inválido.")],
        render_kw={"type": "email", "autocomplete": "email"},
    )


def new_password_field(label="Contraseña", optional=False):
    validators = [Optional()] if optional else [DataRequired()]
    validators += [Length(min=12, max=128), StrongPassword("email")]
    return PasswordField(label, validators=validators, render_kw={"autocomplete": "new-password"})


class ConfirmForm(FlaskForm):
    """Formulario vacío: solo transporta el token CSRF de las acciones POST (borrar, cerrar sesión…)."""


class SearchFormBase(FlaskForm):
    """Búsqueda por GET: no modifica nada, así que no lleva token CSRF."""

    class Meta:
        csrf = False

    q = StringField(
        "Buscar",
        filters=[strip_filter],
        validators=[Optional(), Length(max=SEARCH_MAX, message=f"Máximo {SEARCH_MAX} caracteres."),
                    NoControlChars()],
        render_kw={"type": "search"},
    )
