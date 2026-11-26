"""Registro de servicios: cada ruta pide la INTERFAZ que necesita y recibe su implementación.

create_app() construye las implementaciones una sola vez y las guarda en app.extensions.
Así Services/ (las rutas) no importa nada de Implementation/ directamente.
"""
from flask import current_app

from Implementation.SellerServiceImplementation.SellerServiceImplementation import SellerServiceImplementation
from Implementation.AddressServiceImplementation.AddressServiceImplementation import AddressServiceImplementation
from Implementation.AuthServiceImplementation.AuthServiceImplementation import AuthServiceImplementation
from Implementation.CartServiceImplementation.CartServiceImplementation import CartServiceImplementation
from Implementation.FavoriteServiceImplementation.FavoriteServiceImplementation import FavoriteServiceImplementation
from Implementation.MainServiceImplementation.MainServiceImplementation import MainServiceImplementation
from Implementation.OrderServiceImplementation.OrderServiceImplementation import OrderServiceImplementation
from Implementation.ProductServiceImplementation.ProductServiceImplementation import ProductServiceImplementation
from Implementation.ReviewServiceImplementation.ReviewServiceImplementation import ReviewServiceImplementation
from Implementation.UserServiceImplementation.UserServiceImplementation import UserServiceImplementation


def build_services():
    products = ProductServiceImplementation()
    addresses = AddressServiceImplementation()
    return {
        "seller": SellerServiceImplementation(),
        "main": MainServiceImplementation(products),
        "auth": AuthServiceImplementation(),
        "product": products,
        "user": UserServiceImplementation(products),
        "address": addresses,
        "cart": CartServiceImplementation(),
        "favorite": FavoriteServiceImplementation(),
        "order": OrderServiceImplementation(addresses, products),
        "review": ReviewServiceImplementation(products),
    }


def _service(name):
    return current_app.extensions["services"][name]


def main_service():
    """IMainService"""
    return _service("main")


def seller_service():
    """ISellerService"""
    return _service("seller")


def auth_service():
    """IAuthService"""
    return _service("auth")


def product_service():
    """IProductService"""
    return _service("product")


def user_service():
    """IUserService"""
    return _service("user")


def address_service():
    """IAddressService"""
    return _service("address")


def cart_service():
    """ICartService"""
    return _service("cart")


def favorite_service():
    """IFavoriteService"""
    return _service("favorite")


def order_service():
    """IOrderService"""
    return _service("order")


def review_service():
    """IReviewService"""
    return _service("review")
