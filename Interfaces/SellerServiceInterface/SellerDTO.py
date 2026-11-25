"""DTOs de la tienda del vendedor."""
from dataclasses import dataclass


@dataclass
class SellerInputDTO:
    """Los únicos campos que la persona escribe (seller_id y user_id salen de la sesión)."""

    store_name: str
    description: str = ""


@dataclass
class SellerDTO:
    seller_id: str
    store_name: str
    description: str = ""
