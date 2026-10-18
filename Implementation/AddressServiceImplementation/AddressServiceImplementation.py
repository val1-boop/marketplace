"""Direcciones de envío en RDS MySQL (tabla addresses) con SQLAlchemy.

- Cada consulta filtra por user_id de la SESIÓN: pedir la dirección 7 de otra persona
  devuelve None, igual que una que no existe (anti IDOR, sin revelar que existe).
- Solo se copian los campos del DTO (sin mass assignment: user_id, is_active o
  default_owner nunca vienen del formulario).
- La predeterminada única la garantiza además el índice UNIQUE uq_one_default.
"""
from Core.Extensions import db
from Interfaces.AddressServiceInterface.AddressDTO import AddressDTO, AddressLimitError
from Interfaces.AddressServiceInterface.IAddressService import IAddressService
from Models import MAX_ADDRESSES_PER_USER, Address

EDITABLE = ("label", "recipient_name", "phone", "line1", "line2", "city", "state", "postal_code")


class AddressServiceImplementation(IAddressService):
    @staticmethod
    def _query(user):
        return db.select(Address).where(Address.user_id == user.id, Address.is_active.is_(True))

    def _row(self, user, address_id):
        if not isinstance(address_id, int) or address_id <= 0:
            return None
        return db.session.execute(self._query(user).where(Address.id == address_id)).scalar_one_or_none()

    def list_addresses(self, user):
        rows = db.session.execute(
            self._query(user).order_by(Address.is_default.desc(), Address.created_at.desc(), Address.id.desc())
        ).scalars()
        return [AddressDTO.from_model(row) for row in rows]

    def get_address(self, user, address_id):
        row = self._row(user, address_id)
        return AddressDTO.from_model(row) if row else None

    def _clear_default(self, user):
        db.session.execute(
            db.update(Address).where(Address.user_id == user.id, Address.is_default.is_(True))
            .values(is_default=False)
        )
        db.session.flush()

    def create_address(self, user, data):
        count = db.session.execute(
            db.select(db.func.count()).select_from(Address)
            .where(Address.user_id == user.id, Address.is_active.is_(True))
        ).scalar_one()
        if count >= MAX_ADDRESSES_PER_USER:
            raise AddressLimitError(f"Máximo {MAX_ADDRESSES_PER_USER} direcciones")
        make_default = data.make_default or count == 0  # la primera queda como predeterminada
        if make_default:
            self._clear_default(user)
        row = Address(user_id=user.id, country="MX", is_active=True, is_default=make_default,
                      **{name: getattr(data, name) or ("" if name != "line2" else None) for name in EDITABLE})
        db.session.add(row)
        db.session.commit()
        return AddressDTO.from_model(row)

    def update_address(self, user, address_id, data):
        row = self._row(user, address_id)
        if row is None:
            return None
        for name in EDITABLE:
            setattr(row, name, getattr(data, name) or (None if name == "line2" else ""))
        if data.make_default and not row.is_default:
            self._clear_default(user)
            row.is_default = True
        db.session.commit()
        return AddressDTO.from_model(row)

    def set_default(self, user, address_id):
        row = self._row(user, address_id)
        if row is None:
            return False
        if not row.is_default:
            self._clear_default(user)
            row.is_default = True
            db.session.commit()
        return True

    def deactivate_address(self, user, address_id):
        row = self._row(user, address_id)
        if row is None:
            return False
        was_default = row.is_default
        row.is_active = False
        row.is_default = False
        db.session.flush()
        if was_default:  # otra dirección activa toma su lugar
            other = db.session.execute(self._query(user).order_by(Address.created_at.desc())).scalars().first()
            if other is not None:
                other.is_default = True
        db.session.commit()
        return True

    def shipping_copy(self, user, address_id):
        row = self._row(user, address_id)
        return row.as_shipping() if row else None
