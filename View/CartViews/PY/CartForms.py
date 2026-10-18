"""Formularios del carrito. El precio NUNCA viaja en el formulario: solo producto (en la URL,
validado con lista blanca) y cantidad (1 a 10)."""
from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField
from wtforms.validators import InputRequired, NumberRange

from Interfaces.CartServiceInterface.CartDTO import CART_MAX_QTY


def quantity_field(default=1):
    return IntegerField(
        "Cantidad", default=default,
        validators=[InputRequired(message="Indica la cantidad."),
                    NumberRange(min=1, max=CART_MAX_QTY, message=f"Entre 1 y {CART_MAX_QTY}.")],
        render_kw={"type": "number", "min": 1, "max": CART_MAX_QTY, "step": 1, "inputmode": "numeric"},
    )


class AddToCartForm(FlaskForm):
    quantity = quantity_field()
    next = HiddenField()


class UpdateQuantityForm(FlaskForm):
    quantity = quantity_field()
