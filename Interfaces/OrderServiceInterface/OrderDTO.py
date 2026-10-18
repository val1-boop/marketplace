"""DTOs de pedidos: estados en español, línea de tiempo y acciones permitidas.

Las acciones que se ofrecen en pantalla salen de las mismas reglas que aplica la Lambda
lambdaUpdateOrderStatus; aun así, la Lambda vuelve a comprobarlas (ocultar un botón no
protege nada)."""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from Interfaces.ApiErrors import ApiUnavailableError
from Security import PRODUCT_ID_RE

STATUS_LABELS = {
    "CONFIRMED": "Confirmado",
    "PREPARING": "En preparación",
    "SHIPPED": "Enviado",
    "DELIVERED": "Entregado",
    "CANCELLED": "Cancelado",
}
STATUS_HINTS = {
    "CONFIRMED": "El vendedor recibió tu pedido.",
    "PREPARING": "El vendedor está preparando el paquete.",
    "SHIPPED": "El paquete va en camino.",
    "DELIVERED": "Entregado. ¡Ya puedes opinar sobre el producto!",
    "CANCELLED": "El pedido se canceló y las piezas regresaron al inventario.",
}
STEPS = ("CONFIRMED", "PREPARING", "SHIPPED", "DELIVERED")
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# Mismas reglas que TRANSITIONS en lambdaUpdateOrderStatus.
ACTIONS = {
    "prepare": {"label": "Marcar en preparación", "from": {"seller": {"CONFIRMED"}}},
    "ship": {"label": "Marcar como enviado", "from": {"seller": {"PREPARING"}}},
    "deliver": {"label": "Ya lo recibí", "from": {"buyer": {"SHIPPED"}}},
    "cancel": {"label": "Cancelar pedido", "from": {"buyer": {"CONFIRMED"},
                                                     "seller": {"CONFIRMED", "PREPARING"},
                                                     "admin": {"CONFIRMED", "PREPARING", "SHIPPED"}}},
}
BY_LABELS = {"buyer": "Comprador", "seller": "Vendedor", "admin": "Administración"}


def nice_date(value):
    """'2026-10-15' o '2026-10-15T14:30:00.000Z' → '15 oct 2026' (sin depender del locale)."""
    try:
        if "T" in value:
            parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").date()
        else:
            parsed = date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return "—"
    return f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}"


def nice_datetime(value):
    try:
        parsed = datetime.strptime(value[:16], "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return "—"
    return f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}, {parsed:%H:%M} UTC"


@dataclass
class OrderSummaryDTO:
    order_id: str
    status: str
    title: str
    first_product_id: str
    first_category: str
    total: Decimal
    units: int
    seller_id: str
    created_at: str
    updated_at: str
    estimated_from: str
    estimated_to: str

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, "—")

    @property
    def status_hint(self):
        return STATUS_HINTS.get(self.status, "")

    @property
    def created_label(self):
        return nice_date(self.created_at)

    @property
    def estimate_label(self):
        if self.status in ("DELIVERED", "CANCELLED"):
            return ""
        return f"Llega entre el {nice_date(self.estimated_from)} y el {nice_date(self.estimated_to)}"

    @property
    def short_id(self):
        return self.order_id[-8:]

    @classmethod
    def from_api(cls, raw):
        try:
            summary = cls(
                order_id=str(raw["order_id"]), status=str(raw.get("status") or ""),
                title=str(raw.get("title") or "")[:160],
                first_product_id=str(raw.get("first_product_id") or ""),
                first_category=str(raw.get("first_category") or ""),
                total=Decimal(str(raw.get("total") or "0")), units=int(raw.get("units") or 0),
                seller_id=str(raw.get("seller_id") or ""), created_at=str(raw.get("created_at") or ""),
                updated_at=str(raw.get("updated_at") or ""),
                estimated_from=str(raw.get("estimated_from") or ""),
                estimated_to=str(raw.get("estimated_to") or ""),
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            raise ApiUnavailableError("Pedido con formato inesperado") from error
        if summary.status not in STATUS_LABELS:
            raise ApiUnavailableError("Estado de pedido inesperado")
        if summary.first_product_id and not PRODUCT_ID_RE.match(summary.first_product_id):
            summary.first_product_id = ""
        return summary


@dataclass
class OrderItemDTO:
    product_id: str
    name: str
    category: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal


@dataclass
class OrderDetailDTO(OrderSummaryDTO):
    viewer: str = "buyer"
    items: list = field(default_factory=list)
    shipment: dict = field(default_factory=dict)
    history: list = field(default_factory=list)

    @property
    def actions(self):
        """[(action, label)] que puede hacer quien mira, según el estado actual."""
        return [(name, rule["label"]) for name, rule in ACTIONS.items()
                if self.status in rule["from"].get(self.viewer, set())]

    @property
    def can_cancel(self):
        return any(name == "cancel" for name, _label in self.actions)

    @property
    def steps(self):
        """Línea de tiempo tipo Mercado Libre: [(etiqueta, 'done' | 'current' | 'todo', fecha)]."""
        reached = {h["status"]: h["at"] for h in self.history}
        if self.status == "CANCELLED":
            return [(STATUS_LABELS[s], "done", reached.get(s, "")) for s in STEPS if s in reached] + \
                   [(STATUS_LABELS["CANCELLED"], "cancelled", reached.get("CANCELLED", ""))]
        current = STEPS.index(self.status) if self.status in STEPS else 0
        return [(STATUS_LABELS[s], "done" if i < current else "current" if i == current else "todo",
                 reached.get(s, "")) for i, s in enumerate(STEPS)]

    @property
    def can_review(self):
        return self.viewer == "buyer" and self.status == "DELIVERED"

    @classmethod
    def from_api(cls, raw):
        base = OrderSummaryDTO.from_api(raw)
        try:
            items = [OrderItemDTO(
                product_id=str(i["product_id"]), name=str(i.get("name") or "")[:120],
                category=str(i.get("category") or ""), unit_price=Decimal(str(i.get("unit_price") or "0")),
                quantity=int(i.get("quantity") or 0), subtotal=Decimal(str(i.get("subtotal") or "0")),
            ) for i in raw.get("items") or []]
            shipment = {k: str(v or "")[:120] for k, v in (raw.get("shipment") or {}).items()}
            history = [{"status": str(h.get("status") or ""), "at": str(h.get("at") or ""),
                        "by": BY_LABELS.get(h.get("by"), "—"), "label": STATUS_LABELS.get(h.get("status"), "—"),
                        "when": nice_datetime(str(h.get("at") or ""))}
                       for h in raw.get("history") or []]
        except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
            raise ApiUnavailableError("Pedido con formato inesperado") from error
        viewer = raw.get("viewer") if raw.get("viewer") in ("buyer", "seller", "admin") else "admin"
        return cls(**vars(base), viewer=viewer, items=items, shipment=shipment, history=history)
