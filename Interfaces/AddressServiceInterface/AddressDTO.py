"""DTOs de direcciones de envío."""
from dataclasses import dataclass


class AddressLimitError(Exception):
    """El usuario ya tiene el máximo de direcciones activas."""


@dataclass
class AddressInputDTO:
    """Los únicos campos que la persona escribe (user_id, is_active y country los pone el servidor)."""

    label: str
    recipient_name: str
    phone: str
    line1: str
    line2: str
    city: str
    state: str
    postal_code: str
    make_default: bool = False


@dataclass
class AddressDTO:
    id: int
    label: str
    recipient_name: str
    phone: str
    line1: str
    line2: str
    city: str
    state: str
    postal_code: str
    country: str
    is_default: bool

    @property
    def one_line(self):
        parts = [self.line1, self.line2, f"{self.city}, {self.state}", f"C.P. {self.postal_code}"]
        return ", ".join(p for p in parts if p)

    @classmethod
    def from_model(cls, row):
        return cls(id=row.id, label=row.label, recipient_name=row.recipient_name, phone=row.phone,
                   line1=row.line1, line2=row.line2 or "", city=row.city, state=row.state,
                   postal_code=row.postal_code, country=row.country, is_default=bool(row.is_default))
