"""DTOs del servicio de usuarios (administración)."""
from dataclasses import dataclass


@dataclass
class UserCreateDTO:
    first_name: str
    last_name: str
    email: str
    role: str
    password: str


@dataclass
class UserUpdateDTO:
    """Campos que un administrador puede cambiar; se asignan uno por uno."""

    first_name: str
    last_name: str
    email: str
    role: str
    status: str
    status_reason: str = ""
    new_password: str = ""


@dataclass
class UserResult:
    """Resultado de crear o editar: `user` si salió bien; si no, el error y el campo."""

    user: object = None
    error: str = ""
    field: str = ""
