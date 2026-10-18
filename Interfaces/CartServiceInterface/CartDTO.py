"""DTOs del carrito."""
from dataclasses import dataclass, field
from decimal import Decimal

from Interfaces.ApiErrors import ApiUnavailableError
from Interfaces.ProductServiceInterface.ProductDTO import ProductDTO

CART_MAX_LINES = 10
CART_MAX_QTY = 10


@dataclass
class CartLineDTO:
    product_id: str
    quantity: int
    available: bool
    reason: str
    product: ProductDTO = None

    @property
    def subtotal(self):
        if self.product is None:
            return Decimal("0")
        return self.product.price * self.quantity

    @property
    def max_quantity(self):
        if self.product is None:
            return 1
        return max(1, min(CART_MAX_QTY, self.product.stock))


@dataclass
class CartDTO:
    lines: list = field(default_factory=list)
    total: Decimal = Decimal("0")

    @property
    def units(self):
        return sum(line.quantity for line in self.lines)

    @property
    def has_problems(self):
        return any(not line.available for line in self.lines)

    @property
    def can_checkout(self):
        return bool(self.lines) and not self.has_problems

    @classmethod
    def from_api(cls, body):
        try:
            lines = []
            for raw in body.get("lineas") or []:
                product = raw.get("producto")
                lines.append(CartLineDTO(
                    product_id=str(raw["product_id"]),
                    quantity=int(raw["quantity"]),
                    available=bool(raw.get("available")),
                    reason=str(raw.get("reason") or "")[:80],
                    product=ProductDTO.from_api(product) if isinstance(product, dict) else None,
                ))
            return cls(lines=lines, total=Decimal(str(body.get("total") or "0")))
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            raise ApiUnavailableError("Carrito con formato inesperado") from error
