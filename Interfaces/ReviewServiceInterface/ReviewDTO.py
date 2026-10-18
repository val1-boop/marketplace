"""DTOs de reseñas (estrellas como Amazon)."""
from dataclasses import dataclass, field

from Interfaces.ApiErrors import ApiUnavailableError
from Interfaces.OrderServiceInterface.OrderDTO import nice_date
from Interfaces.ProductServiceInterface.ProductDTO import star_list


@dataclass
class ReviewDTO:
    rating: int
    comment: str
    author_name: str
    created_at: str
    verified: bool = True

    @property
    def stars(self):
        return star_list(self.rating)

    @property
    def date_label(self):
        return nice_date(self.created_at)


@dataclass
class ReviewListDTO:
    reviews: list = field(default_factory=list)
    can_review: bool = False

    @classmethod
    def from_api(cls, body):
        try:
            reviews = []
            for raw in body.get("resenas") or []:
                rating = int(raw.get("rating"))
                if not 1 <= rating <= 5:
                    continue
                reviews.append(ReviewDTO(rating=rating, comment=str(raw.get("comment") or "")[:1000],
                                         author_name=str(raw.get("author_name") or "")[:40],
                                         created_at=str(raw.get("created_at") or ""),
                                         verified=bool(raw.get("verified"))))
            return cls(reviews=reviews, can_review=body.get("puede_opinar") is True)
        except (TypeError, ValueError, AttributeError) as error:
            raise ApiUnavailableError("Reseñas con formato inesperado") from error
