"""Formularios de compra y de cambio de estado del pedido."""
from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, StringField
from wtforms.validators import AnyOf, DataRequired, InputRequired, Length, Optional

from Interfaces.OrderServiceInterface.OrderDTO import ACTIONS
from View.SharedViews.PY.SharedForms import NoControlChars, strip_filter


class CheckoutForm(FlaskForm):
    # Las opciones se llenan con las direcciones DEL USUARIO (choices); cualquier otro ID
    # (por ejemplo, la dirección de otra persona) no pasa la validación.
    address_id = RadioField("Dirección de envío", coerce=int,
                            validators=[InputRequired(message="Elige una dirección de envío.")])

    def set_addresses(self, addresses):
        self.address_id.choices = [(a.id, a.label) for a in addresses]
        if self.address_id.data is None:
            default = next((a.id for a in addresses if a.is_default), None)
            self.address_id.data = default


class OrderActionForm(FlaskForm):
    action = HiddenField(validators=[DataRequired(), AnyOf(list(ACTIONS))])
    reason = StringField("Motivo (opcional)", filters=[strip_filter],
                         validators=[Optional(), Length(min=3, max=200), NoControlChars()],
                         render_kw={"maxlength": 200})
