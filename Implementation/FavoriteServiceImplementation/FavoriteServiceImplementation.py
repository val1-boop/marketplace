"""Favoritos: Flask → API Gateway → lambdaListFavorites / lambdaAddFavorite / lambdaDeleteFavorite."""
from Implementation.SharedImplementation.ApiGatewayClient import actor_of, gateway
from Implementation.SharedImplementation.ShopPaths import product_path
from Interfaces.FavoriteServiceInterface.FavoriteDTO import FavoriteDTO
from Interfaces.FavoriteServiceInterface.IFavoriteService import IFavoriteService


class FavoriteServiceImplementation(IFavoriteService):
    def list_favorites(self, user):
        return FavoriteDTO.list_from_api(gateway().request("GET", "/favorites", actor=actor_of(user)))

    def add_favorite(self, user, product_id):
        gateway().request("PUT", product_path("/favorites", product_id), actor=actor_of(user))

    def remove_favorite(self, user, product_id):
        gateway().request("DELETE", product_path("/favorites", product_id), actor=actor_of(user))
