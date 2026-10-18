"""DTO de favoritos."""
from dataclasses import dataclass

from Interfaces.ApiErrors import ApiUnavailableError
from Interfaces.ProductServiceInterface.ProductDTO import ProductDTO


@dataclass
class FavoriteDTO:
    product_id: str
    added_at: str
    product: ProductDTO = None

    @classmethod
    def list_from_api(cls, body):
        try:
            return [cls(product_id=str(raw["product_id"]), added_at=str(raw.get("added_at") or ""),
                        product=ProductDTO.from_api(raw["producto"]) if isinstance(raw.get("producto"), dict) else None)
                    for raw in body.get("favoritos") or []]
        except (KeyError, TypeError, ValueError) as error:
            raise ApiUnavailableError("Favoritos con formato inesperado") from error
