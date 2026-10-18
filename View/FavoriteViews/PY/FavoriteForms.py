"""Formulario de favoritos: solo CSRF y a dónde regresar (validado con is_safe_redirect)."""
from flask_wtf import FlaskForm
from wtforms import HiddenField


class FavoriteForm(FlaskForm):
    next = HiddenField()
