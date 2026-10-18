"""DTOs (objetos de datos) del servicio de productos.

Un DTO solo transporta datos entre capas: no consulta bases ni APIs. Así las vistas
nunca reciben el JSON crudo del API ni objetos con campos inesperados.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from Interfaces.ProductServiceInterface.ProductErrors import ProductsAPIError
from Security import PRODUCT_ID_RE

LOW_STOCK = 5


def star_list(value):
    """3.6 → ['full', 'full', 'full', 'half', 'empty'] (media estrella desde .25 hasta .75)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    value = min(max(value, 0.0), 5.0)
    stars = []
    for n in range(1, 6):
        if value >= n - 0.25:
            stars.append("full")
        elif value >= n - 0.75:
            stars.append("half")
        else:
            stars.append("empty")
    return stars


def _rating(value):
    try:
        rating = Decimal(str(value or "0")).quantize(Decimal("0.1"))
    except InvalidOperation:
        return Decimal("0.0")
    if not rating.is_finite() or rating < 0 or rating > 5:
        return Decimal("0.0")
    return rating


def _dist(value):
    if not isinstance(value, dict):
        return {}
    clean = {}
    for n in range(1, 6):
        try:
            clean[str(n)] = max(0, int(value.get(str(n), 0) or 0))
        except (TypeError, ValueError):
            clean[str(n)] = 0
    return clean


@dataclass
class ProductDTO:
    """Un producto tal como lo devuelve el API (tabla Products de DynamoDB)."""

    product_id: str
    name: str
    category: str
    price: Decimal
    stock: int
    seller_id: str
    condition: str = "NEW"
    status: str = "ACTIVE"
    blocked_reason: str = None
    version: int = 1
    search_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    rating_avg: Decimal = Decimal("0.0")
    rating_count: int = 0
    rating_dist: dict = field(default_factory=dict)
    sales_count: int = 0

    @property
    def stars(self):
        """Estrellas para pintar: lista de 5 valores 'full' | 'half' | 'empty' (como Amazon)."""
        return star_list(self.rating_avg)

    @property
    def rating_bars(self):
        """[(5, 60), (4, 25)…]: estrella y porcentaje de opiniones (histograma de la ficha)."""
        total = self.rating_count or 0
        return [(n, round(100 * self.rating_dist.get(str(n), 0) / total) if total else 0)
                for n in range(5, 0, -1)]

    @property
    def stock_state(self):
        """in_stock | few_left | sold_out (para el color de la etiqueta y los filtros)."""
        if self.stock <= 0:
            return "sold_out"
        if self.stock <= LOW_STOCK:
            return "few_left"
        return "in_stock"

    @property
    def stock_label(self):
        if self.stock <= 0:
            return "Agotado"
        if self.stock <= LOW_STOCK:
            return "Última pieza" if self.stock == 1 else f"Quedan {self.stock}"
        return "Disponible"

    @classmethod
    def from_api(cls, data):
        """Convierte la respuesta del API en un DTO con tipos fijos; descarta lo demás."""
        try:
            product = cls(
                product_id=str(data["product_id"]),
                name=str(data["name"]),
                category=str(data["category"]),
                price=Decimal(str(data["price"])),
                stock=int(data["stock"]),
                seller_id=str(data.get("seller_id") or ""),
                condition=str(data.get("condition") or "NEW"),
                status=str(data.get("status") or "ACTIVE"),
                blocked_reason=data.get("blocked_reason"),
                version=int(data.get("version") or 1),
                search_name=str(data.get("search_name") or ""),
                created_at=str(data.get("created_at") or ""),
                updated_at=str(data.get("updated_at") or ""),
                description=str(data.get("description") or "")[:2000],
                rating_avg=_rating(data.get("rating_avg")),
                rating_count=max(0, int(data.get("rating_count") or 0)),
                rating_dist=_dist(data.get("rating_dist")),
                sales_count=max(0, int(data.get("sales_count") or 0)),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise ProductsAPIError("Producto con formato inesperado") from error
        if not PRODUCT_ID_RE.match(product.product_id):
            raise ProductsAPIError("product_id inesperado")
        return product


# Compatibilidad: el nombre corto que usan las plantillas y las pruebas.
Product = ProductDTO


@dataclass
class ProductInputDTO:
    """Los únicos 6 campos que un vendedor puede escribir (anti mass assignment)."""

    name: str
    category: str
    price: Decimal
    stock: int
    condition: str
    description: str = ""

    def as_dict(self):
        return {"name": self.name, "category": self.category, "price": self.price,
                "stock": self.stock, "condition": self.condition, "description": self.description}


@dataclass
class CatalogQueryDTO:
    """Filtros del catálogo, ya validados contra listas blancas por el formulario."""

    q: str = ""
    department: str = ""
    category: str = ""
    availability: str = ""
    sort: str = "newest"


@dataclass
class CatalogResultDTO:
    """Resultado del catálogo: productos ordenados + contadores para los filtros."""

    products: list = field(default_factory=list)
    facets: dict = field(default_factory=lambda: {"department": {}, "category": {}, "availability": {}})


@dataclass
class ProductDetailDTO:
    """Ficha de producto: el producto, sus relacionados y datos públicos del vendedor."""

    product: ProductDTO
    related: list
    seller_name: str
    related_names: dict
    is_owner: bool
    seller_user_id: str = None  # solo se llena para administradores
