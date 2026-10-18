"""Formulario de dirección de envío (México). Mismos límites que la tabla addresses y que
la validación de la Lambda lambdaCreateOrder (doble validación)."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from Core.Catalog import MX_STATES
from Interfaces.AddressServiceInterface.AddressDTO import AddressInputDTO
from View.SharedViews.PY.SharedForms import NAME_MSG, NAME_RE, NoControlChars, strip_filter


def _text(label, minimum, maximum, required=True, **kw):
    validators = [DataRequired(message="Campo obligatorio.")] if required else [Optional()]
    validators += [Length(min=minimum, max=maximum), NoControlChars()]
    return StringField(label, filters=[strip_filter], validators=validators, render_kw={"maxlength": maximum, **kw})


class AddressForm(FlaskForm):
    label = _text("Nombre de la dirección (Casa, Trabajo…)", 2, 40)
    recipient_name = StringField(
        "Quién recibe", filters=[strip_filter],
        validators=[DataRequired(), Length(min=2, max=120), NoControlChars(), Regexp(NAME_RE, message=NAME_MSG)],
        render_kw={"maxlength": 120, "autocomplete": "name"},
    )
    phone = StringField(
        "Teléfono (10 dígitos)", filters=[strip_filter],
        validators=[DataRequired(), Regexp(r"^[0-9]{10}$", message="Escribe 10 dígitos, sin espacios.")],
        render_kw={"inputmode": "tel", "maxlength": 10, "autocomplete": "tel-national"},
    )
    line1 = _text("Calle y número", 3, 120, autocomplete="address-line1")
    line2 = _text("Colonia, interior, referencias (opcional)", 0, 120, required=False, autocomplete="address-line2")
    city = _text("Ciudad o municipio", 2, 80, autocomplete="address-level2")
    state = SelectField("Estado", choices=[("", "Elige un estado")] + [(s, s) for s in MX_STATES],
                        validators=[DataRequired(message="Elige un estado.")])
    postal_code = StringField(
        "Código postal", filters=[strip_filter],
        validators=[DataRequired(), Regexp(r"^[0-9]{5}$", message="5 dígitos.")],
        render_kw={"inputmode": "numeric", "maxlength": 5, "autocomplete": "postal-code"},
    )
    make_default = BooleanField("Usar como dirección predeterminada")
    next = HiddenField()

    def to_dto(self):
        return AddressInputDTO(
            label=self.label.data, recipient_name=self.recipient_name.data, phone=self.phone.data,
            line1=self.line1.data, line2=self.line2.data or "", city=self.city.data, state=self.state.data,
            postal_code=self.postal_code.data, make_default=bool(self.make_default.data),
        )
