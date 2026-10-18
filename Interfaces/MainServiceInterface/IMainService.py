"""Contrato del servicio principal: la portada del marketplace y el panel de admin."""
from abc import ABC, abstractmethod


class IMainService(ABC):
    @abstractmethod
    def home(self, viewer):
        """HomeDTO para cualquier visitante (con o sin sesión)."""

    @abstractmethod
    def admin_dashboard(self):
        """AdminDashboardDTO: usuarios, productos bloqueados, accesos fallidos y moderación."""
