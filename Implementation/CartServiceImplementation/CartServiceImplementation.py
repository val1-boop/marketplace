"""Carrito: Flask → API Gateway → lambdaGetCart / lambdaPutCartItem / lambdaDeleteCartItem.

El usuario (x-mkt-actor-user) sale de la sesión; el navegador solo elige producto y cantidad,
y la Lambda vuelve a validar existencias, estado y que no sea un producto propio."""
import logging

from Implementation.SharedImplementation.ApiGatewayClient import actor_of, gateway
from Implementation.SharedImplementation.ShopPaths import product_path
from Interfaces.ApiErrors import ApiUnavailableError
from Interfaces.CartServiceInterface.CartDTO import CART_MAX_QTY, CartDTO
from Interfaces.CartServiceInterface.ICartService import ICartService
from Interfaces.FavoriteServiceInterface.FavoriteDTO import FavoriteDTO

logger = logging.getLogger("marketplace.security")


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= CART_MAX_QTY:
        raise ValueError("Cantidad fuera de rango")
    return value


class CartServiceImplementation(ICartService):
    def get_cart(self, user):
        return CartDTO.from_api(gateway().request("GET", "/cart", actor=actor_of(user)))

    def add_item(self, user, product_id, quantity):
        gateway().request("PUT", product_path("/cart", product_id), actor=actor_of(user),
                          json={"quantity": _quantity(quantity), "mode": "add"})

    def set_quantity(self, user, product_id, quantity):
        gateway().request("PUT", product_path("/cart", product_id), actor=actor_of(user),
                          json={"quantity": _quantity(quantity), "mode": "set"})

    def remove_item(self, user, product_id):
        gateway().request("DELETE", product_path("/cart", product_id), actor=actor_of(user))

    def refresh_counters(self, user, session):
        """Contador del carrito y corazones de favoritos. Si el API no responde, la página
        se sigue mostrando (solo sin contadores) y se reintenta en la siguiente petición."""
        try:
            cart = self.get_cart(user)
            favorites = FavoriteDTO.list_from_api(gateway().request("GET", "/favorites", actor=actor_of(user)))
        except ApiUnavailableError:
            logger.warning("event=shop_counters_unavailable user=%s", user.id)
            return False
        session["cart_count"] = cart.units
        session["fav_ids"] = [f.product_id for f in favorites][:100]
        session["shop_synced"] = True
        return True
