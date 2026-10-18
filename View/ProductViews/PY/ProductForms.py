"""Formularios de productos: publicar/editar, búsqueda del catálogo y motivo de bloqueo."""
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, HiddenField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, Regexp, StopValidation

from Core.Catalog import (
    AVAILABILITY_CHOICES,
    CATEGORY_CHOICES,
    CONDITION_CHOICES,
    DEPARTMENT_CHOICES,
    SORT_CHOICES,
)
from Interfaces.ProductServiceInterface.ProductDTO import CatalogQueryDTO, ProductInputDTO
from View.SharedViews.PY.SharedForms import NoControlChars, SearchFormBase, strip_filter


class StrictMoney:
    """Rechaza NaN/Infinity y más de 2 decimales (StopValidation evita comparar NaN)."""

    def __call__(self, form, field):
        value = field.data
        if value is None:
            return
        message = None
        if not isinstance(value, Decimal) or not value.is_finite():
            message = "Precio inválido."
        elif value.adjusted() > 8:
            message = "Debe estar entre 0.01 y 9,999,999.99."
        elif value.as_tuple().exponent < -2:
            message = "Máximo 2 decimales."
        if message:
            # Se descarta el valor para que volver a pintar el formulario no intente
            # cuantizar NaN/Infinity/1e309 (lanzaría InvalidOperation = error 500).
            field.data = None
            raise StopValidation(message)


class ProductForm(FlaskForm):
    name = StringField(
        "Nombre del producto",
        filters=[strip_filter],
        validators=[DataRequired(), Length(min=3, max=120), NoControlChars()],
    )
    description = TextAreaField(
        "Descripción",
        filters=[strip_filter],
        validators=[DataRequired(message="Describe el producto."), Length(min=10, max=2000),
                    NoControlChars(allow_newlines=True)],
        render_kw={"rows": 6, "maxlength": 2000},
    )
    category = SelectField("Categoría", choices=CATEGORY_CHOICES, validators=[DataRequired()])
    price = DecimalField(
        "Precio (MXN)",
        places=2,
        validators=[InputRequired(message="Indica el precio."), StrictMoney(),
                    NumberRange(min=Decimal("0.01"), max=Decimal("9999999.99"),
                                message="Debe estar entre 0.01 y 9,999,999.99.")],
        render_kw={"type": "number", "step": "0.01", "inputmode": "decimal"},
    )
    stock = IntegerField(
        "Unidades en existencia",
        validators=[InputRequired(message="Indica las unidades."),
                    NumberRange(min=0, max=100000, message="Debe estar entre 0 y 100000.")],
        render_kw={"type": "number", "step": "1"},
    )
    condition = SelectField("Condición", choices=CONDITION_CHOICES, default="NEW")
    # Versión leída al abrir el formulario (bloqueo optimista).
    version = HiddenField(validators=[Optional(), Regexp(r"^\d{1,9}$")])

    def to_dto(self):
        """Copia SOLO los 6 campos editables (el seller_id lo pone el servidor)."""
        return ProductInputDTO(name=self.name.data, category=self.category.data, price=self.price.data,
                               stock=self.stock.data, condition=self.condition.data,
                               description=self.description.data or "")


class MyProductsSearchForm(SearchFormBase):
    """Búsqueda y filtros de 'Mis productos' (solo del vendedor en sesión). Por GET, sin CSRF.
    Todo es lista blanca: un valor fuera de la lista invalida la búsqueda (se muestran todos)."""

    category = SelectField("Categoría", choices=[("", "Todas")] + CATEGORY_CHOICES, default="")
    status = SelectField(
        "Estado",
        choices=[("", "Todos"), ("ACTIVE", "Publicados"), ("BLOCKED", "Bloqueados")],
        default="",
    )


class ReasonForm(FlaskForm):
    reason = StringField(
        "Motivo",
        filters=[strip_filter],
        validators=[DataRequired(), Length(min=5, max=500), NoControlChars()],
    )


class ProductSearchForm(SearchFormBase):
    # Todas son listas blancas: cualquier otro valor invalida la búsqueda (sin resultados).
    department = SelectField("Departamento", choices=[("", "Todos")] + DEPARTMENT_CHOICES, default="")
    category = SelectField("Categoría", choices=[("", "Todas")] + CATEGORY_CHOICES, default="")
    availability = SelectField("Disponibilidad", choices=[("", "Cualquiera")] + AVAILABILITY_CHOICES,
                               default="")
    sort = SelectField("Ordenar por", choices=SORT_CHOICES, default="newest")

    def to_dto(self):
        return CatalogQueryDTO(
            q=self.q.data or "",
            department=self.department.data or "",
            category=self.category.data or "",
            availability=self.availability.data or "",
            sort=self.sort.data or "newest",
        )
