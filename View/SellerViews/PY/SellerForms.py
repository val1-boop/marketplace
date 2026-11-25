"""Formulario de los datos de la tienda."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from Interfaces.SellerServiceInterface.SellerDTO import SellerInputDTO
from View.SharedViews.PY.SharedForms import NoControlChars, strip_filter


class StoreForm(FlaskForm):
    store_name = StringField(
        "Nombre de tu tienda", filters=[strip_filter],
        validators=[DataRequired(message="Escribe el nombre de tu tienda."), Length(min=3, max=80), NoControlChars()],
        render_kw={"maxlength": 80},
    )
    description = TextAreaField(
        "Descripción (opcional)", filters=[strip_filter],
        validators=[Optional(), Length(max=300), NoControlChars(allow_newlines=True)],
        render_kw={"rows": 4, "maxlength": 300},
    )

    def to_dto(self):
        return SellerInputDTO(store_name=self.store_name.data, description=self.description.data or "")
