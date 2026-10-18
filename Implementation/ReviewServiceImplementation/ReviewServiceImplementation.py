"""Reseñas: Flask → API Gateway → lambdaListReviews / lambdaCreateReview.

El nombre público se arma aquí con los datos de la sesión ("Ana P."): nunca se publica el
correo ni el apellido completo, y no se puede firmar con el nombre de otra persona."""
import re

from Implementation.SharedImplementation.ApiGatewayClient import actor_of, gateway
from Implementation.SharedImplementation.ShopPaths import product_path
from Interfaces.ReviewServiceInterface.IReviewService import IReviewService
from Interfaces.ReviewServiceInterface.ReviewDTO import ReviewListDTO

DISPLAY_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '.\-][^\W\d_]+)*\.?\Z")  # igual que en la Lambda


def public_name(user):
    first = (user.first_name or "").strip().split(" ")[0][:30]
    last = (user.last_name or "").strip()[:1]
    name = f"{first} {last}." if last else first
    return name if DISPLAY_NAME_RE.match(name or "") and len(name) >= 2 else "Comprador"


class ReviewServiceImplementation(IReviewService):
    def __init__(self, product_service):
        self.products = product_service

    def list_reviews(self, product_id, viewer):
        # Con sesión se envía el actor para saber si puede opinar; sin sesión, solo lectura.
        actor = actor_of(viewer) if viewer.is_authenticated else None
        body = gateway().request("GET", product_path("/products", product_id, "/reviews"), actor=actor)
        return ReviewListDTO.from_api(body)

    def create_review(self, user, product_id, rating, comment):
        gateway().request("POST", product_path("/products", product_id, "/reviews"), actor=actor_of(user),
                          json={"rating": int(rating), "comment": comment, "author_name": public_name(user)})
        self.products.invalidate_cache()  # cambió el promedio que muestra el catálogo
