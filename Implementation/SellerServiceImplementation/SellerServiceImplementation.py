"""Implementación del servicio de tienda: lee y guarda en la tabla `sellers` (RDS MySQL).

En MySQL guarda con el procedimiento almacenado sp_guardar_tienda; con SQLite (pruebas y modo local)
hace lo mismo con el ORM.
"""
from Core.Extensions import db
from Implementation.SharedImplementation import StoredProcedures
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
        if StoredProcedures.available():
            # user_id y seller_id salen de la sesión; el procedimiento valida todo y guarda de forma atómica.
            try:
                StoredProcedures.save_store(user.id, user.seller_id, data.store_name, data.description)
                db.session.commit()
                return
            except StoredProcedures.ProcedureMissing:
                pass  # falta ejecutar el script 06 en RDS: se guarda con el ORM, igual que con SQLite
        row = db.session.get(Seller, user.seller_id)
        if row is None:
            db.session.add(Seller(seller_id=user.seller_id, user_id=user.id, store_name=data.store_name,
                                  description=data.description or None))
        else:
            row.store_name = data.store_name
            row.description = data.description or None
        db.session.commit()
