"""Implementación del servicio de tienda: lee y guarda en la tabla `sellers` (RDS MySQL)."""
from Core.Extensions import db
from Interfaces.SellerServiceInterface.ISellerService import ISellerService
from Interfaces.SellerServiceInterface.SellerDTO import SellerDTO
from Models import Seller


class SellerServiceImplementation(ISellerService):
    def get_store(self, user):
        if not user.seller_id:
            return None
        row = db.session.get(Seller, user.seller_id)
        if row is None:
            return None
        return SellerDTO(seller_id=row.seller_id, store_name=row.store_name, description=row.description or "")

    def save_store(self, user, data):
        if not user.seller_id:
            raise PermissionError("Solo las cuentas con código de vendedor tienen tienda")
        row = db.session.get(Seller, user.seller_id)
        if row is None:
            db.session.add(Seller(seller_id=user.seller_id, user_id=user.id, store_name=data.store_name,
                                  description=data.description or None))
        else:
            row.store_name = data.store_name
            row.description = data.description or None
        db.session.commit()
