"""Formulario de reseña: de 1 a 5 estrellas y un comentario (10 a 1000 caracteres).
El nombre que se publica lo pone el servidor ("Nombre I."), no el formulario."""
from flask_wtf import FlaskForm
from wtforms import RadioField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length

from View.SharedViews.PY.SharedForms import NoControlChars, strip_filter

RATING_LABELS = {5: "Excelente", 4: "Muy bueno", 3: "Bueno", 2: "Regular", 1: "Malo"}


class ReviewForm(FlaskForm):
    rating = RadioField("Calificación", coerce=int, choices=[(n, RATING_LABELS[n]) for n in (5, 4, 3, 2, 1)],
                        validators=[InputRequired(message="Elige de 1 a 5 estrellas.")])
    comment = TextAreaField(
        "Tu opinión", filters=[strip_filter],
        validators=[DataRequired(message="Escribe tu opinión."), Length(min=10, max=1000),
                    NoControlChars(allow_newlines=True)],
        render_kw={"rows": 4, "maxlength": 1000},
    )
