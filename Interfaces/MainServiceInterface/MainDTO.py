"""DTOs del servicio principal (portada y panel de administración)."""
from dataclasses import dataclass, field


@dataclass
class HomeDTO:
    """Portada pública: departamentos con contadores, estadísticas y lo más reciente."""

    departments: list
    stats: dict
    latest: list
    seller_names: dict
    shop: dict = None  # resumen de la tienda; solo si quien la ve es un vendedor con sesión
    recommended: list = field(default_factory=list)  # "Te recomendamos": mejor calificados


@dataclass
class AdminDashboardDTO:
    stats: dict
    admin_stats: dict
    departments: list
    failures: list = field(default_factory=list)
    actions: list = field(default_factory=list)
