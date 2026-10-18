"""DTOs del servicio de autenticación."""
from dataclasses import dataclass


@dataclass
class RegistrationDTO:
    """Los únicos campos que acepta el registro; rol, estado y seller_id los pone el servidor."""

    first_name: str
    last_name: str
    email: str
    password: str


@dataclass
class PasswordChangeDTO:
    current_password: str
    new_password: str


@dataclass
class PasswordChangeResult:
    """ok=True si se cambió; si no, `field` y `message` dicen qué campo marcar."""

    ok: bool
    field: str = ""
    message: str = ""
